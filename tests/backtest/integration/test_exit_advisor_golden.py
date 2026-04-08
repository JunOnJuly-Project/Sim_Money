"""ExitAdvisor + StopLossGuard 통합 골든 (M5 S14).

WHY: ExitAdvisor 가 매 bar 호출되어 StopLossGuard 의 ForceClose 결정을
     합성 EXIT 신호로 변환해 즉시 청산이 일어나는지 결정론 픽스처로 검증한다.
     advisor 없는 동일 픽스처 대비 거래 수와 손익이 갈라져야 한다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine
from backtest.adapters.outbound.risk_exit_advisor import RiskExitAdvisor
from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.price_bar import PriceBar
from backtest.domain.signal import Side, Signal
from risk.adapters.outbound.stop_loss_guard import StopLossGuard


def _utc(d: int) -> datetime:
    return datetime(2024, 1, d, tzinfo=timezone.utc)


def _bar(ticker: str, close: str, ts: datetime) -> PriceBar:
    c = Decimal(close)
    return PriceBar(timestamp=ts, ticker=ticker, open=c, high=c, low=c, close=c, volume=Decimal("1000"))


def _scenario():
    """100 → 92 → 95 → 98: t2 에서 -8% 로 손절선(5%) 돌파, 사용자 EXIT 는 t4."""
    t = [_utc(d) for d in range(1, 5)]
    config = BacktestConfig(
        initial_capital=Decimal("10000"),
        fee_rate=Decimal("0"),
        slippage_bps=Decimal("0"),
    )
    signals = [
        Signal(timestamp=t[0], ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
        # WHY: 사용자 EXIT 는 t4. advisor ON 이면 t2 에서 강제 청산되어야 한다.
        Signal(timestamp=t[3], ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
    ]
    price_history = {
        "AAPL": [
            _bar("AAPL", "100", t[0]),
            _bar("AAPL", "92", t[1]),
            _bar("AAPL", "95", t[2]),
            _bar("AAPL", "98", t[3]),
        ]
    }
    return signals, price_history, config


class TestExitAdvisorGolden:
    def test_advisor_OFF_는_t4_사용자_EXIT_까지_보유한다(self) -> None:
        signals, price_history, config = _scenario()
        engine = InMemoryBacktestEngine()
        result = engine.run(signals=signals, price_history=price_history, config=config)
        assert len(result.trades) == 1
        # entry=100, exit=98 → pnl < 0
        assert result.trades[0].pnl < Decimal("0")

    def test_advisor_ON_은_t2_에서_강제_청산되어_손실이_더_크다(self) -> None:
        # WHY: max_loss_pct=0.05 → t2 에서 -8% 로 ForceClose, 즉시 EXIT 합성.
        #      사용자 t4 EXIT 는 이미 청산된 포지션이므로 무시된다.
        signals, price_history, config = _scenario()
        advisor = RiskExitAdvisor(guards=[StopLossGuard(max_loss_pct=Decimal("0.05"))])
        engine = InMemoryBacktestEngine(exit_advisor=advisor)
        result = engine.run(signals=signals, price_history=price_history, config=config)

        assert len(result.trades) == 1
        # entry=100, forced exit=92 → pnl = -800
        assert result.trades[0].pnl == Decimal("-800")

    def test_advisor_ON_과_OFF_의_pnl_이_다르다(self) -> None:
        signals, price_history, config = _scenario()

        engine_off = InMemoryBacktestEngine()
        advisor = RiskExitAdvisor(guards=[StopLossGuard(max_loss_pct=Decimal("0.05"))])
        engine_on = InMemoryBacktestEngine(exit_advisor=advisor)

        r_off = engine_off.run(signals=signals, price_history=price_history, config=config)
        r_on = engine_on.run(signals=signals, price_history=price_history, config=config)

        assert r_off.trades[0].pnl != r_on.trades[0].pnl

    def test_advisor_없으면_손절선_미돌파_케이스는_불변이다(self) -> None:
        # WHY: 100 → 110 단조 상승은 ForceClose 트리거 안 함. 골든 케이스 1 과 동일.
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
        price_history = {
            "AAPL": [_bar("AAPL", "100", t1), _bar("AAPL", "110", t2)]
        }
        advisor = RiskExitAdvisor(guards=[StopLossGuard(max_loss_pct=Decimal("0.05"))])
        engine = InMemoryBacktestEngine(exit_advisor=advisor)
        result = engine.run(signals=signals, price_history=price_history, config=config)
        assert len(result.trades) == 1
        assert result.trades[0].pnl == Decimal("1000")
