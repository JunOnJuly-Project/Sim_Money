"""DailyLossLimitGuard (G4) 경계값 테스트 (M5 S6)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from risk.adapters.outbound import DailyLossLimitGuard
from risk.domain import Allow, BlockNew, RiskContext, RiskDomainError

_NOW = datetime(2026, 4, 8, tzinfo=timezone.utc)


def _ctx(equity: Decimal, daily_start: Decimal, candidate: bool = True) -> RiskContext:
    return RiskContext(
        timestamp=_NOW,
        equity=equity,
        peak_equity=max(equity, daily_start),
        daily_start_equity=daily_start,
        candidate_symbol="AAA" if candidate else None,
        candidate_notional=Decimal("100") if candidate else None,
    )


class TestDailyLossLimitGuardInvariants:
    @pytest.mark.parametrize("bad", [Decimal("0"), Decimal("-0.01"), Decimal("2")])
    def test_잘못된_한도_거부(self, bad: Decimal) -> None:
        with pytest.raises(RiskDomainError):
            DailyLossLimitGuard(max_daily_loss=bad)


class TestDailyLossLimitGuard:
    def test_당일_손실_미만이면_Allow(self) -> None:
        guard = DailyLossLimitGuard(max_daily_loss=Decimal("0.03"))
        ctx = _ctx(equity=Decimal("9800"), daily_start=Decimal("10000"))  # -2%
        assert isinstance(guard.check(ctx), Allow)

    def test_당일_손실_정확히_한도면_BlockNew(self) -> None:
        guard = DailyLossLimitGuard(max_daily_loss=Decimal("0.03"))
        ctx = _ctx(equity=Decimal("9700"), daily_start=Decimal("10000"))  # -3%
        assert isinstance(guard.check(ctx), BlockNew)

    def test_당일_손실_초과면_BlockNew(self) -> None:
        guard = DailyLossLimitGuard(max_daily_loss=Decimal("0.03"))
        ctx = _ctx(equity=Decimal("9500"), daily_start=Decimal("10000"))  # -5%
        decision = guard.check(ctx)
        assert isinstance(decision, BlockNew)
        assert "당일" in decision.reason

    def test_수익_중이면_Allow(self) -> None:
        guard = DailyLossLimitGuard(max_daily_loss=Decimal("0.03"))
        ctx = _ctx(equity=Decimal("10500"), daily_start=Decimal("10000"))
        assert isinstance(guard.check(ctx), Allow)

    def test_후보_없으면_Allow(self) -> None:
        guard = DailyLossLimitGuard(max_daily_loss=Decimal("0.03"))
        ctx = _ctx(equity=Decimal("9000"), daily_start=Decimal("10000"), candidate=False)
        assert isinstance(guard.check(ctx), Allow)
