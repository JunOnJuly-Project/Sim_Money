"""RiskEntryFilter 어댑터 통합 테스트 (M5 S8/S9)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from backtest.adapters.outbound.risk_entry_filter import RiskEntryFilter
from backtest.domain.signal import Side, Signal
from risk.adapters.outbound import (
    DrawdownCircuitBreaker,
    PositionLimitGuard,
)

_T = datetime(2026, 4, 8, tzinfo=timezone.utc)


def _sig(ticker: str, strength: str = "1.0") -> Signal:
    return Signal(
        ticker=ticker,
        timestamp=_T,
        side=Side.LONG,
        strength=Decimal(strength),
    )


class TestRiskEntryFilter:
    def test_한도_내_후보는_통과(self) -> None:
        guards = [PositionLimitGuard(max_weight=Decimal("0.5"))]
        f = RiskEntryFilter(guards=guards)
        result = f.filter(
            _T, [_sig("AAA")], available_cash=Decimal("1000"), equity=Decimal("10000")
        )
        assert len(result) == 1

    def test_한도_초과_후보는_제거(self) -> None:
        # max_weight=0.01 → notional 1000 * 1.0 / 1 = 1000 > 100 (= 1% of 10000)
        guards = [PositionLimitGuard(max_weight=Decimal("0.01"))]
        f = RiskEntryFilter(guards=guards)
        result = f.filter(
            _T, [_sig("AAA")], available_cash=Decimal("1000"), equity=Decimal("10000")
        )
        assert result == []

    def test_DD_초과_세션은_모두_차단(self) -> None:
        # 먼저 equity=10000 으로 peak 등록, 이후 equity=7000 (30% DD, 한도 20% 초과)
        guards = [DrawdownCircuitBreaker(max_drawdown=Decimal("0.2"))]
        f = RiskEntryFilter(guards=guards)
        f.filter(_T, [], Decimal("10000"), Decimal("10000"))  # peak 등록
        result = f.filter(
            _T, [_sig("AAA")], available_cash=Decimal("5000"), equity=Decimal("7000")
        )
        assert result == []
