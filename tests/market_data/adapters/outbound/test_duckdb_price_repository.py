"""
DuckDBPriceRepository 어댑터 TDD RED 단계 테스트.

WHY: DuckDBPriceRepository 는 PriceRepository 포트의 DuckDB 구현체다.
     이 파일은 RED 단계 — 어댑터 구현이 없으므로 ImportError 가 기대된다.
     모든 테스트는 ':memory:' DB 를 사용해 디스크를 건드리지 않는다.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

# RED: 아래 임포트는 아직 구현이 없으므로 ImportError 가 발생해야 한다.
from market_data.adapters.outbound.duckdb_price_repository import (
    DuckDBPriceRepository,
)
from market_data.domain.adjusted_price import AdjustedPrice
from market_data.domain.market import Market
from market_data.domain.price_series import PriceSeries
from market_data.domain.ticker import Ticker


# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------


def _ticker(market: Market = Market.KRX, symbol: str = "005930") -> Ticker:
    """Ticker 생성 헬퍼."""
    return Ticker(market=market, symbol=symbol)


def _price(value: float) -> AdjustedPrice:
    """AdjustedPrice 생성 헬퍼."""
    return AdjustedPrice(Decimal(str(value)))


def _series(
    ticker: Ticker,
    entries: list[tuple[date, float]],
) -> PriceSeries:
    """(date, float) 목록으로 PriceSeries 를 생성하는 헬퍼.

    WHY: 각 테스트가 PriceSeries 구성 세부사항을 반복하지 않도록 추출한다.
    """
    prices = tuple((d, _price(v)) for d, v in entries)
    return PriceSeries(ticker=ticker, prices=prices)


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def repo() -> DuckDBPriceRepository:
    """':memory:' DuckDB 를 사용하는 레포지터리 픽스처.

    WHY: 각 테스트가 독립적인 인메모리 DB 인스턴스를 가지도록 함수 스코프로 설정한다.
         테스트 종료 후 close() 를 호출해 연결을 정리한다.
    """
    r = DuckDBPriceRepository(db_path=":memory:")
    yield r
    r.close()


# ---------------------------------------------------------------------------
# 케이스 1: 빈 DB → latest_date == None
# ---------------------------------------------------------------------------


class TestDuckDBPriceRepository_빈DB_latest_date:
    def test_빈_DB에서_latest_date는_None을_반환한다(self, repo: DuckDBPriceRepository) -> None:
        """WHY: 저장된 데이터가 없는 종목은 latest_date 가 None 이어야
        호출자가 '이력 없음' 상태를 명시적으로 처리할 수 있다.
        """
        ticker = _ticker(Market.KRX, "005930")

        result = repo.latest_date(ticker)

        assert result is None


# ---------------------------------------------------------------------------
# 케이스 2: save 후 latest_date 가 가장 최근 날짜
# ---------------------------------------------------------------------------


class TestDuckDBPriceRepository_save_후_latest_date:
    def test_save_후_latest_date는_가장_최근_날짜를_반환한다(
        self, repo: DuckDBPriceRepository
    ) -> None:
        """WHY: 저장된 시계열 중 가장 최근 trade_date 가 latest_date 로 반환돼야
        증분 수집 시 마지막 수집일을 정확히 알 수 있다.
        """
        ticker = _ticker(Market.KRX, "005930")
        series = _series(
            ticker,
            [
                (date(2024, 1, 2), 70_000.0),
                (date(2024, 1, 3), 70_500.0),
                (date(2024, 1, 4), 71_000.0),
            ],
        )

        repo.save(series)
        result = repo.latest_date(ticker)

        assert result == date(2024, 1, 4)


# ---------------------------------------------------------------------------
# 케이스 3: 다른 종목 → 각각 분리 저장
# ---------------------------------------------------------------------------


class TestDuckDBPriceRepository_다른_종목_분리저장:
    def test_서로_다른_종목을_save하면_각각_독립적으로_조회된다(
        self, repo: DuckDBPriceRepository
    ) -> None:
        """WHY: 종목 A 와 종목 B 는 독립적으로 저장·조회돼야 한다.
        한 종목의 latest_date 가 다른 종목에 영향을 주면 안 된다.
        """
        ticker_a = _ticker(Market.KRX, "005930")
        ticker_b = _ticker(Market.KRX, "000660")

        series_a = _series(ticker_a, [(date(2024, 1, 2), 70_000.0)])
        series_b = _series(
            ticker_b,
            [
                (date(2024, 1, 2), 130_000.0),
                (date(2024, 1, 3), 131_000.0),
            ],
        )

        repo.save(series_a)
        repo.save(series_b)

        assert repo.latest_date(ticker_a) == date(2024, 1, 2)
        assert repo.latest_date(ticker_b) == date(2024, 1, 3)


# ---------------------------------------------------------------------------
# 케이스 4: 동일 (market, symbol, date) 재저장 → 멱등 (덮어씀)
# ---------------------------------------------------------------------------


class TestDuckDBPriceRepository_멱등_재저장:
    def test_동일한_날짜를_재저장하면_멱등하게_덮어쓴다(
        self, repo: DuckDBPriceRepository
    ) -> None:
        """WHY: INSERT OR REPLACE 는 동일 PK 에 대해 중복 저장을 허용해야 한다.
        데이터 수집을 재실행해도 중복 row 나 오류가 발생하면 안 된다.
        재저장 후 row 개수가 증가하지 않아야 멱등성이 보장된다.
        """
        ticker = _ticker(Market.KRX, "005930")
        d = date(2024, 1, 2)

        series_first = _series(ticker, [(d, 70_000.0)])
        series_second = _series(ticker, [(d, 75_000.0)])  # 같은 날짜, 다른 가격

        repo.save(series_first)
        repo.save(series_second)

        # 최신 날짜는 여전히 동일한 날짜
        assert repo.latest_date(ticker) == d

        # row 가 1개만 존재해야 한다 (중복 삽입 없음)
        import duckdb

        con = duckdb.connect(":memory:")  # 별도 연결이 아닌 repo 내부 상태를 검증하기 위해
        # repo 의 내부 연결을 활용한 row count 검증
        count = repo._con.execute(
            "SELECT COUNT(*) FROM prices WHERE market = ? AND symbol = ?",
            [ticker.market.value, ticker.symbol],
        ).fetchone()[0]
        assert count == 1


# ---------------------------------------------------------------------------
# 케이스 5: 다른 market 의 같은 symbol → 분리됨
# ---------------------------------------------------------------------------


class TestDuckDBPriceRepository_다른_market_같은_symbol:
    def test_다른_market의_같은_symbol은_분리되어_저장된다(
        self, repo: DuckDBPriceRepository
    ) -> None:
        """WHY: PRIMARY KEY 는 (market, symbol, trade_date) 세 컬럼의 조합이다.
        KRX:AAPL 과 NASDAQ:AAPL 은 symbol 이 같아도 다른 종목이므로
        각각 독립적으로 저장·조회돼야 한다.
        """
        ticker_krx = _ticker(Market.KRX, "AAPL")
        ticker_nasdaq = _ticker(Market.NASDAQ, "AAPL")

        series_krx = _series(ticker_krx, [(date(2024, 1, 2), 100.0)])
        series_nasdaq = _series(
            ticker_nasdaq,
            [
                (date(2024, 1, 2), 185.0),
                (date(2024, 1, 3), 186.0),
            ],
        )

        repo.save(series_krx)
        repo.save(series_nasdaq)

        assert repo.latest_date(ticker_krx) == date(2024, 1, 2)
        assert repo.latest_date(ticker_nasdaq) == date(2024, 1, 3)


# ---------------------------------------------------------------------------
# 케이스 6: save → row count 가 prices 길이와 일치
# ---------------------------------------------------------------------------


class TestDuckDBPriceRepository_row_count:
    def test_save_후_row_count가_PriceSeries_길이와_일치한다(
        self, repo: DuckDBPriceRepository
    ) -> None:
        """WHY: save 가 모든 (date, price) 쌍을 빠짐없이 저장해야
        이후 분석에서 데이터 손실이 없음을 보장한다.
        """
        ticker = _ticker(Market.KRX, "005930")
        entries = [
            (date(2024, 1, 2), 70_000.0),
            (date(2024, 1, 3), 70_500.0),
            (date(2024, 1, 4), 71_000.0),
            (date(2024, 1, 5), 71_500.0),
            (date(2024, 1, 8), 72_000.0),
        ]
        series = _series(ticker, entries)

        repo.save(series)

        count = repo._con.execute(
            "SELECT COUNT(*) FROM prices WHERE market = ? AND symbol = ?",
            [ticker.market.value, ticker.symbol],
        ).fetchone()[0]
        assert count == len(entries)


# ---------------------------------------------------------------------------
# 케이스 7: PriceRepository Protocol 호환성
# ---------------------------------------------------------------------------


class TestDuckDBPriceRepository_Protocol_호환성:
    def test_PriceRepository_Protocol이_요구하는_메서드를_보유한다(
        self, repo: DuckDBPriceRepository
    ) -> None:
        """WHY: DuckDBPriceRepository 는 PriceRepository Protocol 을 구현해야 한다.
        포트-어댑터 계약이 지켜지는지 hasattr 로 구조적 검증을 수행한다.
        런타임에 Protocol 인터페이스가 깨질 경우 이 테스트가 먼저 실패한다.
        """
        assert hasattr(repo, "save"), "save 메서드가 없습니다"
        assert hasattr(repo, "latest_date"), "latest_date 메서드가 없습니다"
        assert callable(repo.save), "save 가 callable 이 아닙니다"
        assert callable(repo.latest_date), "latest_date 가 callable 이 아닙니다"
