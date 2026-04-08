"""DrawdownCircuitBreaker (G3) 경계값 테스트 (M5 S4)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from risk.adapters.outbound import DrawdownCircuitBreaker
from risk.domain import Allow, BlockNew, RiskContext, RiskDomainError

_NOW = datetime(2026, 4, 8, tzinfo=timezone.utc)


def _ctx(equity: Decimal, peak: Decimal, with_candidate: bool = True) -> RiskContext:
    return RiskContext(
        timestamp=_NOW,
        equity=equity,
        peak_equity=peak,
        daily_start_equity=peak,
        candidate_symbol="AAA" if with_candidate else None,
        candidate_notional=Decimal("100") if with_candidate else None,
    )


class TestDrawdownCircuitBreakerInvariants:
    @pytest.mark.parametrize("bad", [Decimal("0"), Decimal("-0.1"), Decimal("1.5")])
    def test_잘못된_max_drawdown_거부(self, bad: Decimal) -> None:
        with pytest.raises(RiskDomainError):
            DrawdownCircuitBreaker(max_drawdown=bad)


class TestDrawdownCircuitBreaker:
    def test_DD_미만이면_Allow(self) -> None:
        guard = DrawdownCircuitBreaker(max_drawdown=Decimal("0.2"))
        ctx = _ctx(equity=Decimal("9000"), peak=Decimal("10000"))  # DD 10%
        assert isinstance(guard.check(ctx), Allow)

    def test_DD_정확히_한도면_Allow(self) -> None:
        guard = DrawdownCircuitBreaker(max_drawdown=Decimal("0.2"))
        ctx = _ctx(equity=Decimal("8000"), peak=Decimal("10000"))  # 정확히 20%
        assert isinstance(guard.check(ctx), Allow)

    def test_DD_초과면_BlockNew(self) -> None:
        guard = DrawdownCircuitBreaker(max_drawdown=Decimal("0.2"))
        ctx = _ctx(equity=Decimal("7500"), peak=Decimal("10000"))  # 25%
        decision = guard.check(ctx)
        assert isinstance(decision, BlockNew)
        assert "드로다운" in decision.reason

    def test_후보_없으면_Allow(self) -> None:
        guard = DrawdownCircuitBreaker(max_drawdown=Decimal("0.2"))
        ctx = _ctx(equity=Decimal("5000"), peak=Decimal("10000"), with_candidate=False)
        assert isinstance(guard.check(ctx), Allow)
