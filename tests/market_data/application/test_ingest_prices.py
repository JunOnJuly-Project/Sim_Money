"""
IngestPrices 유스케이스 TDD RED 단계 테스트.

WHY: 헥사고날 아키텍처에서 유스케이스는 포트(인터페이스)에만 의존해야 한다.
     인메모리 Fake 구현으로 포트 계약을 검증하고, 유스케이스의 모든 분기(증분 적재,
     최초 적재, 빈 응답, 이미 최신)를 외부 인프라 없이 결정론적으로 테스트한다.
     이 파일은 RED 단계 — 포트/유스케이스 구현이 없으므로 ImportError 가 기대된다.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import pytest

# RED: 아래 세 임포트는 아직 구현이 없으므로 ImportError 가 발생해야 한다.
from market_data.application.ports import MarketDataSource, PriceRepository
from market_data.application.ingest_prices import IngestPrices
from market_data.domain.adjusted_price import AdjustedPrice
from market_data.domain.market import Market
from market_data.domain.price_series import PriceSeries
from market_data.domain.ticker import Ticker


# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------

def _ticker(symbol: str = "005930") -> Ticker:
    """테스트 전용 기본 Ticker."""
    return Ticker(market=Market.KRX, symbol=symbol)


def _make_series(
    ticker: Ticker,
    start: date,
    days: int,
    base_price: float = 70_000.0,
) -> PriceSeries:
    """연속 날짜 days 개짜리 PriceSeries 를 생성하는 헬퍼.

    WHY: 개별 테스트가 날짜 계산 세부사항을 반복하지 않도록 추출한다.
    """
    prices = tuple(
        (start + timedelta(days=i), AdjustedPrice(Decimal(str(base_price + i))))
        for i in range(days)
    )
    return PriceSeries(ticker=ticker, prices=prices)


# ---------------------------------------------------------------------------
# Fake 포트 구현 (인메모리, Protocol 계약 준수)
# ---------------------------------------------------------------------------

class FakeMarketDataSource:
    """MarketDataSource 포트의 인메모리 테스트 더블.

    WHY: 실제 FinanceDataReader 없이도 소스 응답을 주입할 수 있어
         네트워크·I/O 의존성 없이 유스케이스 로직을 검증한다.
    """

    def __init__(self, series: Optional[PriceSeries] = None) -> None:
        # fetch 호출 시 반환할 시계열 (None 이면 데이터 없음을 의미)
        self._series = series
        # 실제로 어떤 인자로 호출됐는지 기록
        self.calls: list[tuple[Ticker, date, date]] = []

    def fetch(
        self, ticker: Ticker, start: date, end: date
    ) -> Optional[PriceSeries]:
        """fetch 호출을 기록한 뒤 주입된 시계열을 반환한다."""
        self.calls.append((ticker, start, end))
        return self._series


class FakePriceRepository:
    """PriceRepository 포트의 인메모리 테스트 더블.

    WHY: DuckDB 연결 없이 save/latest_date 계약을 인메모리로 구현해
         유스케이스 저장 동작을 빠르게 검증한다.
    """

    def __init__(self, existing_latest: Optional[date] = None) -> None:
        # latest_date 질의 시 반환할 날짜 (None 이면 데이터 없음)
        self._existing_latest = existing_latest
        # save 에 전달된 PriceSeries 를 순서대로 기록
        self.saved: list[PriceSeries] = []

    def save(self, series: PriceSeries) -> None:
        """저장 요청을 인메모리 목록에 기록한다."""
        self.saved.append(series)

    def latest_date(self, ticker: Ticker) -> Optional[date]:
        """사전 주입된 최신 날짜를 반환한다."""
        return self._existing_latest


# ---------------------------------------------------------------------------
# 케이스 1: 최초 적재 (latest_date == None)
# ---------------------------------------------------------------------------

class TestIngestPrices_최초_적재:
    def test_latest_date가_None이면_start부터_end까지_fetch한다(self):
        """WHY: 저장된 데이터가 없으면 사용자가 지정한 start 부터 적재해야 한다."""
        ticker = _ticker()
        start = date(2024, 1, 2)
        end = date(2024, 1, 5)
        series = _make_series(ticker, start=start, days=4)

        source = FakeMarketDataSource(series=series)
        repo = FakePriceRepository(existing_latest=None)
        use_case = IngestPrices(source=source, repository=repo)

        result = use_case.execute(ticker=ticker, start=start, end=end)

        # fetch 는 정확히 1회, start~end 범위로 호출돼야 한다
        assert len(source.calls) == 1
        called_ticker, called_start, called_end = source.calls[0]
        assert called_start == start
        assert called_end == end

        # save 는 정확히 1회 호출돼야 한다
        assert len(repo.saved) == 1

        # 반환값은 저장된 row 수(시계열 길이)와 같아야 한다
        assert result == len(series)

    def test_최초_적재_시_save에_전달된_series_ticker가_일치한다(self):
        """WHY: 포트 계약에서 save 의 인자는 올바른 ticker 를 보유해야 한다."""
        ticker = _ticker()
        start = date(2024, 1, 2)
        end = date(2024, 1, 3)
        series = _make_series(ticker, start=start, days=2)

        source = FakeMarketDataSource(series=series)
        repo = FakePriceRepository(existing_latest=None)

        IngestPrices(source=source, repository=repo).execute(
            ticker=ticker, start=start, end=end
        )

        assert repo.saved[0].ticker == ticker


# ---------------------------------------------------------------------------
# 케이스 2: 증분 적재 (latest_date 존재)
# ---------------------------------------------------------------------------

class TestIngestPrices_증분_적재:
    def test_latest_date가_있으면_다음날부터_fetch한다(self):
        """WHY: 이미 보유한 데이터를 중복 적재하지 않도록 latest_date + 1 부터 시작해야 한다."""
        ticker = _ticker()
        existing_latest = date(2024, 1, 5)
        expected_fetch_start = existing_latest + timedelta(days=1)  # 2024-01-06
        end = date(2024, 1, 10)

        # 2024-01-06 ~ 2024-01-10 (5일치)
        series = _make_series(ticker, start=expected_fetch_start, days=5)

        source = FakeMarketDataSource(series=series)
        repo = FakePriceRepository(existing_latest=existing_latest)

        result = IngestPrices(source=source, repository=repo).execute(
            ticker=ticker, start=date(2024, 1, 2), end=end
        )

        _, called_start, called_end = source.calls[0]
        assert called_start == expected_fetch_start
        assert called_end == end
        assert result == 5

    def test_증분_적재_시_repository에_전달된_ticker가_일치한다(self):
        """WHY: 증분 적재에서도 save 인자의 ticker 동등성을 보장해야 한다."""
        ticker = _ticker("AAPL")
        existing_latest = date(2024, 3, 10)
        fetch_start = existing_latest + timedelta(days=1)
        end = date(2024, 3, 15)
        series = _make_series(ticker, start=fetch_start, days=5)

        source = FakeMarketDataSource(series=series)
        repo = FakePriceRepository(existing_latest=existing_latest)

        IngestPrices(source=source, repository=repo).execute(
            ticker=ticker, start=date(2024, 1, 2), end=end
        )

        assert repo.saved[0].ticker == ticker


# ---------------------------------------------------------------------------
# 케이스 3: source 가 None 반환 (빈 응답)
# ---------------------------------------------------------------------------

class TestIngestPrices_빈_응답:
    def test_source가_None을_반환하면_save가_호출되지_않는다(self):
        """WHY: 데이터 없음을 나타내는 None 에 대해 빈 저장 시도를 막아야 한다."""
        ticker = _ticker()
        source = FakeMarketDataSource(series=None)
        repo = FakePriceRepository(existing_latest=None)

        result = IngestPrices(source=source, repository=repo).execute(
            ticker=ticker, start=date(2024, 1, 2), end=date(2024, 1, 5)
        )

        assert len(repo.saved) == 0
        assert result == 0


# ---------------------------------------------------------------------------
# 케이스 4: latest_date == end (이미 최신 상태)
# ---------------------------------------------------------------------------

class TestIngestPrices_이미_최신:
    def test_latest_date가_end와_같으면_fetch없이_0을_반환한다(self):
        """WHY: 이미 end 날짜까지 보유한 경우 불필요한 네트워크 호출을 막아야 한다."""
        ticker = _ticker()
        end = date(2024, 1, 10)

        source = FakeMarketDataSource(series=None)
        repo = FakePriceRepository(existing_latest=end)

        result = IngestPrices(source=source, repository=repo).execute(
            ticker=ticker, start=date(2024, 1, 2), end=end
        )

        # fetch 자체가 호출되지 않아야 한다
        assert len(source.calls) == 0
        assert len(repo.saved) == 0
        assert result == 0

    def test_latest_date가_end보다_이후이면_fetch없이_0을_반환한다(self):
        """WHY: latest_date 가 end 를 초과하는 경우도 이미 최신으로 취급해야 한다."""
        ticker = _ticker()
        end = date(2024, 1, 10)

        source = FakeMarketDataSource(series=None)
        # latest_date 가 end 보다 나중
        repo = FakePriceRepository(existing_latest=date(2024, 1, 15))

        result = IngestPrices(source=source, repository=repo).execute(
            ticker=ticker, start=date(2024, 1, 2), end=end
        )

        assert len(source.calls) == 0
        assert result == 0
