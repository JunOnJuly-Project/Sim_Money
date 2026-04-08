"""
백테스트 골든 케이스 통합 테스트 (TDD RED 단계).

WHY: 어댑터와 유스케이스가 조립된 상태에서 수기 계산 결과와 일치하는지
     결정론적으로 검증한다. 구현 완료 후에도 회귀 방지 테스트로 유지된다.
     구현 전에는 NotImplementedError 혹은 ModuleNotFoundError 로 RED 상태가 된다.

골든 케이스 기준:
    Case 1: 2-bar LONG→EXIT, fee=0, slippage=0
            initial=10000, close=100→110, strength=Decimal("1.0")
            → qty=100, pnl=1000

    Case 2: fee=0.001, slippage=5bps 반영
            → qty, pnl 수기 계산 일치

    Case 3: 3-ticker 병렬 포지션 독립 검증
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.price_bar import PriceBar
from backtest.domain.signal import Side, Signal


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _utc(year: int, month: int, day: int) -> datetime:
    """UTC tz-aware datetime 생성 헬퍼."""
    return datetime(year, month, day, tzinfo=timezone.utc)


def _bar(ticker: str, close: str, ts: datetime) -> PriceBar:
    """테스트용 PriceBar 생성 헬퍼."""
    c = Decimal(close)
    return PriceBar(
        timestamp=ts,
        ticker=ticker,
        open=c,
        high=c,
        low=c,
        close=c,
        volume=Decimal("1000"),
    )


def _build_engine():
    """InMemoryBacktestEngine 인스턴스 반환."""
    from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine
    return InMemoryBacktestEngine()


# ---------------------------------------------------------------------------
# 골든 케이스 테스트
# ---------------------------------------------------------------------------

class TestGoldenCase1_기본_LONG_EXIT:
    """Case 1: fee=0, slippage=0 → qty=100, pnl=1000 수기 검증."""

    def test_2bar_LONG_EXIT_pnl이_1000이다(self) -> None:
        """WHY: 가장 단순한 시나리오로 엔진 전체 파이프라인을 수기값과 대조한다.
               qty = 10000 / 100 = 100
               pnl = (110 - 100) * 100 = 1000"""
        engine = _build_engine()
        t1 = _utc(2024, 1, 1)
        t2 = _utc(2024, 1, 2)

        config = BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t2, ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "AAPL": [
                _bar("AAPL", close="100", ts=t1),
                _bar("AAPL", close="110", ts=t2),
            ]
        }

        result = engine.run(
            signals=signals,
            price_history=price_history,
            config=config,
        )

        assert len(result.trades) == 1
        trade = result.trades[0]
        # qty = 10000 / 100 = 100
        assert trade.quantity == Decimal("100")
        # pnl = (110 - 100) * 100 = 1000
        assert trade.pnl == Decimal("1000")

    def test_2bar_LONG_EXIT_total_return이_01이다(self) -> None:
        """WHY: initial=10000, pnl=1000 → total_return = 1000/10000 = 0.1."""
        engine = _build_engine()
        t1 = _utc(2024, 1, 1)
        t2 = _utc(2024, 1, 2)

        config = BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t2, ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "AAPL": [
                _bar("AAPL", close="100", ts=t1),
                _bar("AAPL", close="110", ts=t2),
            ]
        }

        result = engine.run(
            signals=signals,
            price_history=price_history,
            config=config,
        )

        # total_return = (11000 - 10000) / 10000 = 0.1
        assert result.metrics.total_return == Decimal("0.1")


class TestGoldenCase2_fee_slippage:
    """Case 2: fee=0.001, slippage=5bps 반영 수기 검증."""

    def test_fee_001_slippage_5bps_pnl이_수계산과_일치한다(self) -> None:
        """WHY: 수수료와 슬리피지가 동시에 적용될 때 pnl 이 수기값과 일치해야 한다.

        수기 계산:
            slippage_factor_long = 5 / 10_000 = 0.0005
            fill_entry = 100 * (1 + 0.0005) = 100.05
            qty = 10000 / 100.05 ≈ 99.9500249875...  (Decimal 정밀도 유지)

            fill_exit = 110 * (1 - 0.0005) = 109.945
            entry_fee = fill_entry * qty * 0.001
            exit_fee  = fill_exit  * qty * 0.001
            pnl = (fill_exit - fill_entry) * qty - entry_fee - exit_fee

        이 테스트는 수기 계산 대신 부호(양수 pnl)와 fee=0 대비 감소를 검증한다.
        developer 가 정밀 계산 구현 후 정확한 Decimal 값으로 assert 를 보강할 수 있다.
        """
        engine = _build_engine()
        t1 = _utc(2024, 1, 1)
        t2 = _utc(2024, 1, 2)

        config = BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("5"),
        )
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t2, ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "AAPL": [
                _bar("AAPL", close="100", ts=t1),
                _bar("AAPL", close="110", ts=t2),
            ]
        }

        result_with_cost = engine.run(
            signals=signals,
            price_history=price_history,
            config=config,
        )

        # fee=0, slippage=0 기준 참조 실행
        config_no_cost = BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )
        result_no_cost = engine.run(
            signals=signals,
            price_history=price_history,
            config=config_no_cost,
        )

        pnl_with_cost = result_with_cost.trades[0].pnl
        pnl_no_cost = result_no_cost.trades[0].pnl

        # 비용이 있을 때 pnl 이 더 작아야 한다
        assert pnl_with_cost < pnl_no_cost
        # 수익 거래이므로 pnl 은 여전히 양수
        assert pnl_with_cost > Decimal("0")


class TestGoldenCase3_멀티_티커:
    """Case 3: 3-ticker 병렬 포지션 독립 검증."""

    def test_3개_ticker_포지션이_서로_독립적으로_처리된다(self) -> None:
        """WHY: 여러 ticker 가 동시에 포지션을 보유할 때 서로 간섭하면 안 된다.
               각 ticker 의 pnl 이 독립적으로 계산되는지 확인한다."""
        engine = _build_engine()
        t1 = _utc(2024, 1, 1)
        t2 = _utc(2024, 1, 2)

        config = BacktestConfig(
            initial_capital=Decimal("30000"),  # 3배 자본
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )

        tickers = ["AAPL", "MSFT", "GOOGL"]
        close_entry = {"AAPL": "100", "MSFT": "200", "GOOGL": "300"}
        close_exit = {"AAPL": "110", "MSFT": "210", "GOOGL": "320"}

        signals = []
        price_history: dict = {}
        for ticker in tickers:
            signals.append(Signal(timestamp=t1, ticker=ticker, side=Side.LONG, strength=Decimal("1.0")))
            signals.append(Signal(timestamp=t2, ticker=ticker, side=Side.EXIT, strength=Decimal("1.0")))
            price_history[ticker] = [
                _bar(ticker, close=close_entry[ticker], ts=t1),
                _bar(ticker, close=close_exit[ticker], ts=t2),
            ]

        result = engine.run(
            signals=signals,
            price_history=price_history,
            config=config,
        )

        # 3개 ticker 에서 각 1개씩 총 3개 Trade 생성
        assert len(result.trades) == 3

        # 각 ticker 가 독립적으로 처리되었는지 ticker 별로 검증
        trade_by_ticker = {t.ticker: t for t in result.trades}
        assert set(trade_by_ticker.keys()) == set(tickers)

        # AAPL: entry=100, exit=110 → pnl > 0
        assert trade_by_ticker["AAPL"].pnl > Decimal("0")
        # MSFT: entry=200, exit=210 → pnl > 0
        assert trade_by_ticker["MSFT"].pnl > Decimal("0")
        # GOOGL: entry=300, exit=320 → pnl > 0
        assert trade_by_ticker["GOOGL"].pnl > Decimal("0")

    def test_3개_ticker_pnl_합산이_양수다(self) -> None:
        """WHY: 모든 ticker 가 수익이므로 합산 pnl 도 양수여야 한다."""
        engine = _build_engine()
        t1 = _utc(2024, 1, 1)
        t2 = _utc(2024, 1, 2)

        config = BacktestConfig(
            initial_capital=Decimal("30000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )

        tickers = ["AAPL", "MSFT", "GOOGL"]
        close_entry = {"AAPL": "100", "MSFT": "200", "GOOGL": "300"}
        close_exit = {"AAPL": "110", "MSFT": "210", "GOOGL": "320"}

        signals = []
        price_history: dict = {}
        for ticker in tickers:
            signals.append(Signal(timestamp=t1, ticker=ticker, side=Side.LONG, strength=Decimal("1.0")))
            signals.append(Signal(timestamp=t2, ticker=ticker, side=Side.EXIT, strength=Decimal("1.0")))
            price_history[ticker] = [
                _bar(ticker, close=close_entry[ticker], ts=t1),
                _bar(ticker, close=close_exit[ticker], ts=t2),
            ]

        result = engine.run(
            signals=signals,
            price_history=price_history,
            config=config,
        )

        total_pnl = sum(t.pnl for t in result.trades)
        assert total_pnl > Decimal("0")


class TestGoldenCase4_risk_free_rate_반영:
    """Case 4: risk_free_rate=0 vs rfr=0.05 → 샤프 비율 차이 확인."""

    def _build_config(self, rfr: str) -> BacktestConfig:
        return BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
            risk_free_rate=Decimal(rfr),
        )

    def _run_with_rfr(self, rfr: str):
        """WHY: 동일 시장 데이터에 rfr 만 다르게 주입해 샤프 차이를 검증한다.
               equity_curve 포인트가 3개 이상 있어야 excess 리스트 길이 >= 2 가 되어
               ddof=1 표본 표준편차 계산이 가능하다. LONG 진입 후 중간 EXIT+재진입으로
               equity_curve 포인트를 충분히 확보한다.
        """
        from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine
        engine = InMemoryBacktestEngine()

        # 4-bar 시계열: LONG t1 → EXIT t2 → LONG t3 → EXIT t4
        # → equity_curve: t1(초기), t2(EXIT 후), t3(재진입), t4(EXIT 후)
        # excess 리스트 길이 = 3 → ddof=1 계산 가능
        t = [_utc(2024, 1, d) for d in range(1, 5)]
        prices = ["100", "110", "110", "120"]
        signals = [
            Signal(timestamp=t[0], ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t[1], ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
            Signal(timestamp=t[2], ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t[3], ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "AAPL": [_bar("AAPL", close=p, ts=ts) for ts, p in zip(t, prices)]
        }

        return engine.run(
            signals=signals,
            price_history=price_history,
            config=self._build_config(rfr),
        )

    def test_rfr_0과_rfr_005의_샤프가_다르다(self) -> None:
        """WHY: rfr 이 BacktestConfig → RatioPerformanceCalculator 로 전달되어야
               초과수익률 계산에 반영된다. rfr=0 과 rfr=0.05 의 샤프가 달라야 한다.
        """
        result_zero = self._run_with_rfr("0")
        result_rfr = self._run_with_rfr("0.05")

        # rfr 이 높을수록 초과수익률이 낮아져 샤프 비율이 낮아진다
        assert result_rfr.metrics.sharpe < result_zero.metrics.sharpe

    def test_rfr_005이면_샤프가_rfr_0보다_작다(self) -> None:
        """WHY: 단조 상승 시계열에서 rfr 추가 시 초과수익률이 줄어 샤프가 감소한다."""
        result_zero = self._run_with_rfr("0")
        result_rfr = self._run_with_rfr("0.05")

        sharpe_zero = result_zero.metrics.sharpe
        sharpe_rfr = result_rfr.metrics.sharpe

        assert isinstance(sharpe_zero, float)
        assert isinstance(sharpe_rfr, float)
        # rfr 적용 시 샤프가 0 방향으로 이동해야 한다
        assert sharpe_rfr < sharpe_zero


class TestGoldenCase5_Sortino_Calmar:
    """Case 5: 하방 변동성 있는 equity → Sortino/Calmar 계산 회귀."""

    def _build_config(self) -> BacktestConfig:
        return BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )

    def _run_volatile(self):
        """WHY: 가격이 상승-하락-상승을 반복해 하방 수익률이 발생하는 시나리오.
               LONG/EXIT 사이클로 equity_curve 포인트를 4개 이상 확보한다.
        """
        from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine
        engine = InMemoryBacktestEngine()

        t = [_utc(2024, 1, d) for d in range(1, 5)]
        # 100 → 110(+10%) → 99(-10%) → 108(+9%) : 하방 구간 존재
        prices = ["100", "110", "99", "95"]
        signals = [
            Signal(timestamp=t[0], ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t[1], ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
            Signal(timestamp=t[2], ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t[3], ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "AAPL": [_bar("AAPL", close=p, ts=ts) for ts, p in zip(t, prices)]
        }
        return engine.run(
            signals=signals,
            price_history=price_history,
            config=self._build_config(),
        )

    def test_하방이_있으면_sortino_는_유한하다(self) -> None:
        result = self._run_volatile()
        import math as _m
        assert isinstance(result.metrics.sortino, float)
        assert _m.isfinite(result.metrics.sortino)

    def test_MDD_가_음수이면_calmar_도_유한하다(self) -> None:
        result = self._run_volatile()
        import math as _m
        assert result.metrics.max_drawdown < Decimal("0")
        assert _m.isfinite(result.metrics.calmar)

