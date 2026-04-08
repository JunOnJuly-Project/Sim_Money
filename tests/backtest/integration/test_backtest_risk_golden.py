"""백테스트 + RiskEntryFilter 골든 회귀 (M5 S10).

WHY: S12 에서 추가한 RiskEntryFilter 의 notional 추정
     (`strength * available_cash / N`) 이 실제 StrengthPositionSizer.size_group
     (`strength / N` × initial_cash) 과 일치하는지 결정론 픽스처로 검증한다.
     동시에 (a) 가드 ON 시 BlockNew 로 진입이 막히고 (b) equity_curve 가 가드 OFF 와
     갈라지는지 확인해 회귀 안전망을 마련한다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine
from backtest.adapters.outbound.risk_entry_filter import RiskEntryFilter
from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.price_bar import PriceBar
from backtest.domain.signal import Side, Signal
from risk.adapters.outbound.position_limit_guard import PositionLimitGuard


def _utc(d: int) -> datetime:
    return datetime(2024, 1, d, tzinfo=timezone.utc)


def _bar(ticker: str, close: str, ts: datetime) -> PriceBar:
    c = Decimal(close)
    return PriceBar(timestamp=ts, ticker=ticker, open=c, high=c, low=c, close=c, volume=Decimal("1000"))


def _scenario():
    """initial=10000, AAPL 100→110 LONG/EXIT 단일 후보."""
    t1, t2 = _utc(1), _utc(2)
    config = BacktestConfig(
        initial_capital=Decimal("10000"),
        fee_rate=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    signals = [
        Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
        Signal(timestamp=t2, ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
    ]
    price_history = {"AAPL": [_bar("AAPL", "100", t1), _bar("AAPL", "110", t2)]}
    return signals, price_history, config


class TestRiskGolden_PositionLimit_차단:
    """가드 ON 시 BlockNew 로 진입이 차단되어 거래 0건이 되어야 한다."""

    def test_position_limit_05이면_strength10_단일후보_진입이_차단된다(self) -> None:
        # WHY: notional = 1.0 * 10000 / 1 = 10000, equity=10000, cap=0.5*10000=5000
        #      → 10000 > 5000 이므로 PositionLimitGuard 가 BlockNew 반환.
        signals, price_history, config = _scenario()
        risk_filter = RiskEntryFilter(guards=[PositionLimitGuard(max_weight=Decimal("0.5"))])
        engine = InMemoryBacktestEngine(entry_filter=risk_filter)

        result = engine.run(signals=signals, price_history=price_history, config=config)

        assert len(result.trades) == 0
        assert result.metrics.total_return == Decimal("0")

    def test_가드_OFF_와_ON_의_equity_curve_가_갈라진다(self) -> None:
        # WHY: 동일 픽스처에서 가드 ON/OFF 결과가 달라야 회귀 감지 가능.
        signals, price_history, config = _scenario()

        engine_off = InMemoryBacktestEngine()
        engine_on = InMemoryBacktestEngine(
            entry_filter=RiskEntryFilter(guards=[PositionLimitGuard(max_weight=Decimal("0.5"))])
        )

        result_off = engine_off.run(signals=signals, price_history=price_history, config=config)
        result_on = engine_on.run(signals=signals, price_history=price_history, config=config)

        # OFF: 골든 케이스 1과 동일 (pnl=1000, total_return=0.1)
        assert len(result_off.trades) == 1
        assert result_off.trades[0].pnl == Decimal("1000")
        assert result_off.metrics.total_return == Decimal("0.1")

        # ON: 차단되어 0 거래 / 0 수익
        assert len(result_on.trades) == 0
        assert result_on.metrics.total_return == Decimal("0")


class TestRiskGolden_PositionLimit_허용:
    """notional 이 cap 이내면 가드 ON 이어도 골든 결과가 보존되어야 한다.

    WHY: 이 케이스가 RiskEntryFilter 의 notional 추정이
         실제 사이저(`strength * initial_cash / N`) 와 일치함을 증명한다.
         만약 추정이 어긋나면 cap 경계 근처에서 거짓 차단이 발생한다.
    """

    def test_position_limit_10이면_골든_케이스1_과_동일하다(self) -> None:
        signals, price_history, config = _scenario()
        # cap = 1.0 → notional 10000 ≤ 10000, 통과해야 한다.
        risk_filter = RiskEntryFilter(guards=[PositionLimitGuard(max_weight=Decimal("1.0"))])
        engine = InMemoryBacktestEngine(entry_filter=risk_filter)

        result = engine.run(signals=signals, price_history=price_history, config=config)

        assert len(result.trades) == 1
        assert result.trades[0].quantity == Decimal("100")
        assert result.trades[0].pnl == Decimal("1000")
        assert result.metrics.total_return == Decimal("0.1")
