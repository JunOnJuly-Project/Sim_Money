"""
그룹 단위 포트폴리오 사이징 통합 테스트 (TDD RED 단계).

WHY: 동일 timestamp 에 여러 LONG 신호가 들어올 때 PortfolioPositionSizer 가
     형제 신호를 인지하고 포트폴리오 제약을 일괄 적용해야 한다.
     기존 cash_per_signal 균등 분배 방식은 EqualWeightStrategy/ScoreWeightedStrategy 가
     "포트폴리오 관점"으로 동작하지 못하는 구조적 한계가 있다.

검증 핵심:
    3개 LONG 신호 + PortfolioPositionSizer(EqualWeight, cash_buffer=0.1)
    → 각 포지션의 weight = (1 - 0.1) / 3 = 0.3
    → qty = available_cash * 0.3 / price
    → 3개 weight 합 = 0.9
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from portfolio.adapters.outbound.equal_weight_strategy import EqualWeightStrategy
from portfolio.domain.constraints import PortfolioConstraints

from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine
from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor
from backtest.adapters.outbound.portfolio_position_sizer import PortfolioPositionSizer
from backtest.application.use_cases.run_backtest import RunBacktest
from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator
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


def _make_sizer(cash_buffer: str = "0.1") -> PortfolioPositionSizer:
    """PortfolioPositionSizer(EqualWeight) 생성 헬퍼."""
    return PortfolioPositionSizer(
        strategy=EqualWeightStrategy(),
        constraints=PortfolioConstraints(
            cash_buffer=Decimal(cash_buffer),
        ),
    )


# ---------------------------------------------------------------------------
# 그룹 사이징 핵심 테스트
# ---------------------------------------------------------------------------

class TestGroupSizing_3신호_EqualWeight:
    """동일 timestamp 3개 LONG 신호 → EqualWeight 그룹 사이징 검증."""

    def test_3개_신호의_각_weight가_0_3이다(self) -> None:
        """cash_buffer=0.1, 3개 EqualWeight → 각 weight = 0.3.

        WHY: PortfolioPositionSizer.size_group 이 형제 신호를 한 번에 받아
             EqualWeightStrategy.compute 에 전달하면 cash_buffer 차감 후
             균등 배분이 이루어진다. 신호별 독립 호출 방식은 이 검증이 불가하다.
        """
        sizer = _make_sizer(cash_buffer="0.1")
        ts = _utc(2024, 1, 1)
        signals = [
            Signal(timestamp=ts, ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=ts, ticker="MSFT", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=ts, ticker="TSLA", side=Side.LONG, strength=Decimal("1.0")),
        ]

        weights = sizer.size_group(signals, Decimal("10000"))

        # EqualWeight(3개) + cash_buffer=0.1 → 각 weight = (1-0.1)/3 = 0.3
        expected = Decimal("0.3")
        assert len(weights) == 3
        for w in weights:
            assert w == expected, f"예상 weight={expected}, 실제={w}"

    def test_3개_weight_합이_0_9다(self) -> None:
        """3개 weight 합 = 1 - cash_buffer = 0.9.

        WHY: 현금 버퍼가 정확히 적용되면 투자 비중 합이 1 - cash_buffer 여야 한다.
             합이 1 을 초과하면 레버리지가 발생하는 버그이다.
        """
        sizer = _make_sizer(cash_buffer="0.1")
        ts = _utc(2024, 1, 1)
        signals = [
            Signal(timestamp=ts, ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=ts, ticker="MSFT", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=ts, ticker="TSLA", side=Side.LONG, strength=Decimal("1.0")),
        ]

        weights = sizer.size_group(signals, Decimal("10000"))
        total = sum(weights)

        assert total == Decimal("0.9"), f"weight 합 예상=0.9, 실제={total}"

    def test_3개_신호_엔드투엔드_수량_검증(self) -> None:
        """엔진 end-to-end: 3신호 진입 후 각 qty = available_cash * 0.3 / price.

        WHY: size_group 이 엔진 루프에 올바르게 연결되면
             각 포지션 수량이 포트폴리오 비중을 정확히 반영한다.
             qty = 10000 * 0.3 / 100 = 30.
        """
        sizer = _make_sizer(cash_buffer="0.1")
        executor = InMemoryTradeExecutor()
        calculator = RatioPerformanceCalculator(risk_free_rate=0.0)
        use_case = RunBacktest(
            trade_executor=executor,
            performance_calculator=calculator,
            sizer=sizer,
        )

        ts = _utc(2024, 1, 1)
        ts_exit = _utc(2024, 1, 2)

        signals = [
            Signal(timestamp=ts, ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=ts, ticker="MSFT", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=ts, ticker="TSLA", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=ts_exit, ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
            Signal(timestamp=ts_exit, ticker="MSFT", side=Side.EXIT, strength=Decimal("1.0")),
            Signal(timestamp=ts_exit, ticker="TSLA", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "AAPL": [_bar("AAPL", "100", ts), _bar("AAPL", "100", ts_exit)],
            "MSFT": [_bar("MSFT", "100", ts), _bar("MSFT", "100", ts_exit)],
            "TSLA": [_bar("TSLA", "100", ts), _bar("TSLA", "100", ts_exit)],
        }
        config = BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )

        result = use_case.execute(signals=signals, price_history=price_history, config=config)

        assert len(result.trades) == 3
        # 각 qty = 10000 * 0.3 / 100 = 30
        expected_qty = Decimal("30")
        for trade in result.trades:
            assert trade.quantity == expected_qty, (
                f"{trade.ticker} qty 예상={expected_qty}, 실제={trade.quantity}"
            )


class TestGroupSizing_StrengthSizer_기본동작:
    """StrengthPositionSizer 의 size_group 기본 동작 검증."""

    def test_strength_sizer_size_group_단일신호(self) -> None:
        """StrengthPositionSizer.size_group([signal], cash) → [signal.strength].

        WHY: 기존 동작과 100% 호환되어야 한다.
             단일 신호의 size_group 결과가 size 결과와 동일해야 한다.
        """
        from backtest.adapters.outbound.strength_position_sizer import StrengthPositionSizer

        sizer = StrengthPositionSizer()
        ts = _utc(2024, 1, 1)
        signal = Signal(timestamp=ts, ticker="AAPL", side=Side.LONG, strength=Decimal("0.7"))

        weights = sizer.size_group([signal], Decimal("10000"))

        assert len(weights) == 1
        assert weights[0] == Decimal("0.7")

    def test_strength_sizer_size_group_복수신호(self) -> None:
        """StrengthPositionSizer.size_group 은 strength / N 으로 정규화된 weight 를 반환한다.

        WHY: 엔진 루프가 initial_cash_for_group * weight / price 로 수량을 계산하므로
             기존 동작(cash/N * strength / price)과 동일 결과를 내려면
             size_group 이 strength / N 을 반환해야 한다.
             N=2 인 경우: AAPL=0.6/2=0.3, MSFT=0.4/2=0.2.
        """
        from backtest.adapters.outbound.strength_position_sizer import StrengthPositionSizer

        sizer = StrengthPositionSizer()
        ts = _utc(2024, 1, 1)
        signals = [
            Signal(timestamp=ts, ticker="AAPL", side=Side.LONG, strength=Decimal("0.6")),
            Signal(timestamp=ts, ticker="MSFT", side=Side.LONG, strength=Decimal("0.4")),
        ]

        weights = sizer.size_group(signals, Decimal("10000"))

        # strength / N: 0.6/2=0.3, 0.4/2=0.2
        assert weights[0] == Decimal("0.6") / Decimal("2")
        assert weights[1] == Decimal("0.4") / Decimal("2")


class TestGroupSizing_RunBacktest_기본사이저:
    """RunBacktest 기본 sizer(StrengthPositionSizer) 동작 유지 검증."""

    def test_기본_sizer_주입시_기존_동작_유지(self) -> None:
        """RunBacktest(sizer=None) → StrengthPositionSizer 기본 동작.

        WHY: sizer 파라미터를 추가해도 기존 호출 코드가 변경 없이
             동일 결과를 반환해야 한다(하위 호환성).
        """
        calculator = RatioPerformanceCalculator(risk_free_rate=0.0)
        executor = InMemoryTradeExecutor()
        use_case = RunBacktest(
            trade_executor=executor,
            performance_calculator=calculator,
        )

        ts = _utc(2024, 2, 1)
        ts_exit = _utc(2024, 2, 2)
        signals = [
            Signal(timestamp=ts, ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=ts_exit, ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "AAPL": [_bar("AAPL", "100", ts), _bar("AAPL", "110", ts_exit)],
        }
        config = BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )

        result = use_case.execute(signals=signals, price_history=price_history, config=config)

        assert len(result.trades) == 1
        # qty = 10000 * 1.0 / 100 = 100, pnl = (110-100)*100 = 1000
        assert result.trades[0].quantity == Decimal("100")
        assert result.trades[0].pnl == Decimal("1000")
