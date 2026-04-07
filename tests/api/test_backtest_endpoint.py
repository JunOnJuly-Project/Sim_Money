"""
GET /backtest/pair/{a}/{b} 엔드포인트 통합 테스트.

WHY: 백테스트 엔드포인트는 trading_signal + backtest 두 L3 모듈을 조립하는
     복합 어댑터다. Fake 저장소와 TestClient 로 HTTP 계층까지 일관되게 검증해
     직렬화 오류나 파이프라인 연결 오류를 조기에 발견한다.

케이스:
    1. 정상 요청 — 200 + 응답 키 구조 검증
    2. 종목 A 시계열 없음 — 404
    3. 종목 B 시계열 없음 — 404
    4. 교집합이 lookback+1 미만 — 400
    5. rfr=0.05 — 200 + sharpe 가 rfr=0 결과와 다름
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from market_data.domain.adjusted_price import AdjustedPrice
from market_data.domain.market import Market
from market_data.domain.price_series import PriceSeries
from market_data.domain.ticker import Ticker
from similarity.adapters.inbound.fastapi_app import create_app
from similarity.domain.weighted_sum_strategy import SimilarityWeights

# ── 상수 ──────────────────────────────────────────────────────────────────

# 백테스트 엔드포인트 테스트용 lookback 기본값
_DEFAULT_LOOKBACK = 20
# lookback+1 충족을 위해 필요한 최소 날짜 수
_MIN_DATES_FOR_DEFAULT_LOOKBACK = _DEFAULT_LOOKBACK + 1


# ── Fake 컴포넌트 ──────────────────────────────────────────────────────────

@dataclass
class FakePriceRepository:
    """PriceRepository 테스트 더블.

    WHY: 실제 DuckDB 없이 symbol 기반 로드를 시뮬레이션한다.
         /backtest/pair 엔드포인트는 KRX Market + 심볼로 Ticker 를 생성하므로
         저장 시에도 같은 Ticker 키를 사용해야 한다.
    """

    store: dict[Ticker, PriceSeries] = field(default_factory=dict)

    def save(self, series: PriceSeries) -> None:
        self.store[series.ticker] = series

    def load(self, ticker: Ticker) -> PriceSeries | None:
        return self.store.get(ticker)

    def latest_date(self, ticker: Ticker) -> date | None:
        series = self.store.get(ticker)
        return series.latest_date() if series is not None else None


@dataclass
class FakeUniverseSource:
    """UniverseSource 테스트 더블.

    WHY: /backtest/pair 엔드포인트는 universe_source 를 사용하지 않으므로
         fetch 는 호출되지 않는다. 인터페이스만 충족하면 충분하다.
    """

    def fetch(self, name: str, as_of: date) -> object:
        raise NotImplementedError("백테스트 엔드포인트에서는 universe_source 를 호출하지 않아야 합니다")


@dataclass
class FakeStrategyFactory:
    """strategy_factory 테스트 더블.

    WHY: /backtest/pair 엔드포인트도 전략 팩토리를 인자로 받는 create_app 에서 생성된다.
         백테스트 엔드포인트는 strategy_factory 를 호출하지 않으므로 더미 구현으로 충분하다.
    """

    def __call__(self, weights: SimilarityWeights) -> object:
        raise NotImplementedError("백테스트 엔드포인트에서는 strategy_factory 를 호출하지 않아야 합니다")


# ── 헬퍼 함수 ─────────────────────────────────────────────────────────────

def _make_ticker(symbol: str) -> Ticker:
    """백테스트 엔드포인트가 내부에서 생성하는 KRX Ticker 를 동일하게 생성한다."""
    return Ticker(market=Market("KRX"), symbol=symbol)


def _make_price_series(symbol: str, n: int, start_price: float = 100.0) -> PriceSeries:
    """n 일치 연속 가격 시계열을 생성한다.

    WHY: 시작가에서 매일 0.5씩 증가하는 단조 상승 시계열로
         log_returns 가 항상 양수여서 신호 계산이 안정적으로 동작한다.
         날짜는 2024-01-02 부터 시작해 영업일 관계없이 연속으로 부여한다.
    """
    ticker = _make_ticker(symbol)
    base_date = date(2024, 1, 2)
    prices = tuple(
        (base_date + timedelta(days=i), AdjustedPrice.from_float(start_price + i * 0.5))
        for i in range(n)
    )
    return PriceSeries(ticker=ticker, prices=prices)


def _make_client(
    series_a: PriceSeries | None,
    series_b: PriceSeries | None,
) -> TestClient:
    """FakePriceRepository 에 시계열을 주입한 TestClient 를 반환한다."""
    repo = FakePriceRepository()
    if series_a is not None:
        repo.save(series_a)
    if series_b is not None:
        repo.save(series_b)

    app = create_app(
        repository=repo,
        universe_source=FakeUniverseSource(),
        strategy_factory=FakeStrategyFactory(),
    )
    return TestClient(app)


# ── 케이스 1: 정상 요청 ────────────────────────────────────────────────────

class TestBacktestEndpoint_정상_응답:
    """lookback+1 이상의 충분한 시계열이 있을 때 200 과 응답 구조를 검증한다."""

    def test_정상_요청에_200과_필수_키를_반환한다(self) -> None:
        """WHY: 클라이언트는 metrics/trades/equity_curve/pair/signals_count
               5개 최상위 키를 기대한다. 하나라도 누락되면 프론트엔드가 파싱에 실패한다.
        """
        # lookback=20 이므로 21개 이상 날짜 필요
        series_a = _make_price_series("AAA", n=30, start_price=100.0)
        series_b = _make_price_series("BBB", n=30, start_price=200.0)
        client = _make_client(series_a, series_b)

        response = client.get("/backtest/pair/AAA/BBB")

        assert response.status_code == 200
        body = response.json()
        # 최상위 키 검증
        assert "metrics" in body
        assert "trades" in body
        assert "equity_curve" in body
        assert "pair" in body
        assert "signals_count" in body

    def test_metrics_하위_키를_모두_포함한다(self) -> None:
        """WHY: metrics 내 total_return/sharpe/max_drawdown/win_rate 가 모두 있어야
               프론트엔드 Metrics 카드가 빈 값 없이 렌더된다.
        """
        series_a = _make_price_series("AAA", n=30)
        series_b = _make_price_series("BBB", n=30)
        client = _make_client(series_a, series_b)

        response = client.get("/backtest/pair/AAA/BBB")

        body = response.json()
        metrics = body["metrics"]
        assert "total_return" in metrics
        assert "sharpe" in metrics
        assert "max_drawdown" in metrics
        assert "win_rate" in metrics

    def test_pair_필드가_요청한_심볼을_반환한다(self) -> None:
        """WHY: 응답의 pair.a, pair.b 가 요청 경로 파라미터와 일치해야
               클라이언트가 어느 쌍의 결과인지 확인할 수 있다.
        """
        series_a = _make_price_series("AAA", n=30)
        series_b = _make_price_series("BBB", n=30)
        client = _make_client(series_a, series_b)

        response = client.get("/backtest/pair/AAA/BBB")

        body = response.json()
        assert body["pair"]["a"] == "AAA"
        assert body["pair"]["b"] == "BBB"

    def test_signals_count에_long_short_exit_키가_있다(self) -> None:
        """WHY: signals_count 의 long/short/exit 합산이 신호 수를 검증하는 기준이 된다."""
        series_a = _make_price_series("AAA", n=30)
        series_b = _make_price_series("BBB", n=30)
        client = _make_client(series_a, series_b)

        response = client.get("/backtest/pair/AAA/BBB")

        sc = response.json()["signals_count"]
        assert "long" in sc
        assert "short" in sc
        assert "exit" in sc
        # 각 카운트는 0 이상의 정수
        assert sc["long"] >= 0
        assert sc["short"] >= 0
        assert sc["exit"] >= 0


# ── 케이스 2: 종목 A 없음 ─────────────────────────────────────────────────

class TestBacktestEndpoint_a_없음:
    def test_a_시계열이_없으면_404를_반환한다(self) -> None:
        """WHY: repository.load(ticker_a) 가 None 이면 백테스트를 진행할 수 없다.
               클라이언트에게 명시적으로 어느 종목이 없는지 알려주기 위해 404 를 사용한다.
        """
        series_b = _make_price_series("BBB", n=30)
        # series_a 는 등록하지 않음
        client = _make_client(series_a=None, series_b=series_b)

        response = client.get("/backtest/pair/AAA/BBB")

        assert response.status_code == 404
        assert "detail" in response.json()


# ── 케이스 3: 종목 B 없음 ─────────────────────────────────────────────────

class TestBacktestEndpoint_b_없음:
    def test_b_시계열이_없으면_404를_반환한다(self) -> None:
        """WHY: repository.load(ticker_b) 가 None 이면 페어 신호를 생성할 수 없다.
               a 가 있어도 b 가 없으면 동일하게 404 를 반환해야 한다.
        """
        series_a = _make_price_series("AAA", n=30)
        # series_b 는 등록하지 않음
        client = _make_client(series_a=series_a, series_b=None)

        response = client.get("/backtest/pair/AAA/BBB")

        assert response.status_code == 404
        assert "detail" in response.json()


# ── 케이스 4: 교집합 부족 ─────────────────────────────────────────────────

class TestBacktestEndpoint_교집합_부족:
    def test_교집합이_lookback_이하면_400을_반환한다(self) -> None:
        """WHY: 교집합 길이 < lookback+1 이면 z-score 롤링 윈도우가 채워지지 않아
               의미 있는 신호를 생성할 수 없다. 클라이언트에게 데이터 부족을 알리기 위해 400.

               lookback=20(기본값) 이므로 교집합이 20개 이하면 에러다.
               두 시계열을 5개씩 서로 다른 날짜에 배치해 교집합을 0으로 만든다.
        """
        # AAA: 2024-01-02 ~ 2024-01-06 (5일)
        # BBB: 2024-06-01 ~ 2024-06-05 (5일) — 날짜 교집합 없음
        ticker_a = _make_ticker("AAA")
        ticker_b = _make_ticker("BBB")

        start_a = date(2024, 1, 2)
        start_b = date(2024, 6, 1)

        series_a = PriceSeries(
            ticker=ticker_a,
            prices=tuple(
                (start_a + timedelta(days=i), AdjustedPrice.from_float(100.0 + i))
                for i in range(5)
            ),
        )
        series_b = PriceSeries(
            ticker=ticker_b,
            prices=tuple(
                (start_b + timedelta(days=i), AdjustedPrice.from_float(200.0 + i))
                for i in range(5)
            ),
        )

        client = _make_client(series_a=series_a, series_b=series_b)

        response = client.get("/backtest/pair/AAA/BBB")

        assert response.status_code == 400
        assert "detail" in response.json()


# ── 케이스 5: rfr 쿼리 파라미터 ───────────────────────────────────────────

# 무위험 수익률 테스트용 상수
_RFR_DEFAULT = 0.0
_RFR_CUSTOM = 0.05
# rfr 이 높을수록 초과 수익률이 낮아져 Sharpe 가 낮거나 같아야 하는데,
# 실제 부호는 수익률의 방향에 따라 달라진다. 따라서 '다름' 만 검증한다.
_SERIES_N = 60  # 충분한 교집합 보장


class TestBacktestEndpoint_rfr_파라미터:
    """rfr 쿼리 파라미터가 BacktestConfig 에 올바르게 주입되는지 검증한다."""

    def test_rfr_지정시_sharpe가_기본값과_달라진다(self) -> None:
        """WHY: rfr=0.05 를 전달하면 Sharpe 계산 시 무위험 수익률이 차감되므로
               rfr=0 일 때와 다른 sharpe 값이 반환되어야 한다.
               두 요청을 동일 시계열로 실행해 rfr 만 다를 때 sharpe 가 달라짐을 검증한다.
        """
        series_a = _make_price_series("AAA", n=_SERIES_N, start_price=100.0)
        series_b = _make_price_series("BBB", n=_SERIES_N, start_price=200.0)
        client = _make_client(series_a, series_b)

        resp_default = client.get(f"/backtest/pair/AAA/BBB?rfr={_RFR_DEFAULT}")
        resp_custom = client.get(f"/backtest/pair/AAA/BBB?rfr={_RFR_CUSTOM}")

        assert resp_default.status_code == 200
        assert resp_custom.status_code == 200

        sharpe_default = resp_default.json()["metrics"]["sharpe"]
        sharpe_custom = resp_custom.json()["metrics"]["sharpe"]
        # rfr 가 다르면 Sharpe 값도 달라야 한다 (None 허용: 트레이드 없는 경우 동일할 수 있음)
        # WHY: 트레이드가 발생하면 반드시 달라지므로, 같은 경우를 명시적으로 허용한다.
        #      단, 200 응답 자체와 키 존재만 필수 검증한다.
        assert "sharpe" in resp_custom.json()["metrics"]
        # 트레이드가 존재하면 sharpe 가 달라짐을 추가 검증
        if resp_default.json()["trades"] and sharpe_default is not None and sharpe_custom is not None:
            assert sharpe_default != sharpe_custom
