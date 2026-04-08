"""PositionLimitGuard (G1) 경계값 테스트 (M5 S3)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from risk.adapters.outbound import PositionLimitGuard
from risk.domain import (
    Allow,
    BlockNew,
    PositionSnapshot,
    RiskContext,
    RiskDomainError,
)

_NOW = datetime(2026, 4, 8, tzinfo=timezone.utc)


def _ctx(**overrides) -> RiskContext:
    kwargs = dict(
        timestamp=_NOW,
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
        daily_start_equity=Decimal("10000"),
    )
    kwargs.update(overrides)
    return RiskContext(**kwargs)


class TestPositionLimitGuardInvariants:
    @pytest.mark.parametrize("bad", [Decimal("0"), Decimal("-0.1"), Decimal("1.5")])
    def test_잘못된_max_weight_거부(self, bad: Decimal) -> None:
        with pytest.raises(RiskDomainError):
            PositionLimitGuard(max_weight=bad)


class TestPositionLimitGuardBoundaries:
    """경계값 3종: 한도 미만 / 정확히 한도 / 한도 초과."""

    def test_후보_비중이_한도_미만이면_Allow(self) -> None:
        guard = PositionLimitGuard(max_weight=Decimal("0.3"))
        ctx = _ctx(
            candidate_symbol="AAA",
            candidate_notional=Decimal("2000"),  # 20% < 30%
        )
        assert isinstance(guard.check(ctx), Allow)

    def test_후보_비중이_정확히_한도면_Allow(self) -> None:
        guard = PositionLimitGuard(max_weight=Decimal("0.3"))
        ctx = _ctx(
            candidate_symbol="AAA",
            candidate_notional=Decimal("3000"),  # 정확히 30%
        )
        assert isinstance(guard.check(ctx), Allow)

    def test_후보_비중이_한도_초과면_BlockNew(self) -> None:
        guard = PositionLimitGuard(max_weight=Decimal("0.3"))
        ctx = _ctx(
            candidate_symbol="AAA",
            candidate_notional=Decimal("3500"),  # 35% > 30%
        )
        decision = guard.check(ctx)
        assert isinstance(decision, BlockNew)
        assert "AAA" in decision.reason


class TestPositionLimitGuardExisting:
    def test_기존_포지션_한도_초과_시_BlockNew(self) -> None:
        guard = PositionLimitGuard(max_weight=Decimal("0.3"))
        over = PositionSnapshot(
            symbol="AAA",
            quantity=Decimal("100"),
            entry_price=Decimal("30"),
            current_price=Decimal("40"),  # notional = 4000 > 3000
        )
        ctx = _ctx(positions=(over,))
        decision = guard.check(ctx)
        assert isinstance(decision, BlockNew)

    def test_기존_포지션_과_후보_합산이_한도_초과면_BlockNew(self) -> None:
        guard = PositionLimitGuard(max_weight=Decimal("0.3"))
        existing = PositionSnapshot(
            symbol="AAA",
            quantity=Decimal("10"),
            entry_price=Decimal("100"),
            current_price=Decimal("150"),  # notional = 1500
        )
        ctx = _ctx(
            positions=(existing,),
            candidate_symbol="AAA",
            candidate_notional=Decimal("2000"),  # 1500 + 2000 = 3500 > 3000
        )
        assert isinstance(guard.check(ctx), BlockNew)

    def test_후보_없고_기존_포지션_한도_내면_Allow(self) -> None:
        guard = PositionLimitGuard(max_weight=Decimal("0.5"))
        pos = PositionSnapshot(
            symbol="AAA",
            quantity=Decimal("10"),
            entry_price=Decimal("100"),
            current_price=Decimal("100"),
        )
        ctx = _ctx(positions=(pos,))
        assert isinstance(guard.check(ctx), Allow)
