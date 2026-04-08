"""StopLossGuard (G2) 경계값 테스트 (M5 S5)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from risk.adapters.outbound import StopLossGuard
from risk.domain import (
    Allow,
    ForceClose,
    PositionSnapshot,
    RiskContext,
    RiskDomainError,
)

_NOW = datetime(2026, 4, 8, tzinfo=timezone.utc)


def _pos(symbol: str, entry: Decimal, current: Decimal) -> PositionSnapshot:
    return PositionSnapshot(
        symbol=symbol,
        quantity=Decimal("10"),
        entry_price=entry,
        current_price=current,
    )


def _ctx(*positions: PositionSnapshot) -> RiskContext:
    return RiskContext(
        timestamp=_NOW,
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
        daily_start_equity=Decimal("10000"),
        positions=tuple(positions),
    )


class TestStopLossGuardInvariants:
    @pytest.mark.parametrize("bad", [Decimal("0"), Decimal("-0.1"), Decimal("1.5")])
    def test_잘못된_max_loss_pct_거부(self, bad: Decimal) -> None:
        with pytest.raises(RiskDomainError):
            StopLossGuard(max_loss_pct=bad)


class TestStopLossGuard:
    def test_손실률_한도_미만이면_Allow(self) -> None:
        guard = StopLossGuard(max_loss_pct=Decimal("0.05"))
        # -3% 손실
        ctx = _ctx(_pos("AAA", Decimal("100"), Decimal("97")))
        assert isinstance(guard.check(ctx), Allow)

    def test_손실률_정확히_한도면_ForceClose(self) -> None:
        guard = StopLossGuard(max_loss_pct=Decimal("0.05"))
        # 정확히 -5%
        ctx = _ctx(_pos("AAA", Decimal("100"), Decimal("95")))
        decision = guard.check(ctx)
        assert isinstance(decision, ForceClose)
        assert decision.symbol == "AAA"

    def test_손실률_초과면_ForceClose(self) -> None:
        guard = StopLossGuard(max_loss_pct=Decimal("0.05"))
        # -7%
        ctx = _ctx(_pos("AAA", Decimal("100"), Decimal("93")))
        assert isinstance(guard.check(ctx), ForceClose)

    def test_수익_중인_포지션은_Allow(self) -> None:
        guard = StopLossGuard(max_loss_pct=Decimal("0.05"))
        ctx = _ctx(_pos("AAA", Decimal("100"), Decimal("110")))
        assert isinstance(guard.check(ctx), Allow)

    def test_포지션_없으면_Allow(self) -> None:
        guard = StopLossGuard(max_loss_pct=Decimal("0.05"))
        ctx = _ctx()
        assert isinstance(guard.check(ctx), Allow)
