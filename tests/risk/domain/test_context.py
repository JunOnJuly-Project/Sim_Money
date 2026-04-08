"""RiskContext / PositionSnapshot 값 객체 불변식 테스트 (M5 S1)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from risk.domain import PositionSnapshot, RiskContext, RiskDomainError


_NOW = datetime(2026, 4, 8, tzinfo=timezone.utc)


def _valid_snapshot(**overrides) -> PositionSnapshot:
    kwargs = dict(
        symbol="AAA",
        quantity=Decimal("10"),
        entry_price=Decimal("100"),
        current_price=Decimal("110"),
    )
    kwargs.update(overrides)
    return PositionSnapshot(**kwargs)


def _valid_context(**overrides) -> RiskContext:
    kwargs = dict(
        timestamp=_NOW,
        equity=Decimal("10000"),
        peak_equity=Decimal("12000"),
        daily_start_equity=Decimal("11000"),
    )
    kwargs.update(overrides)
    return RiskContext(**kwargs)


class TestPositionSnapshot:
    def test_유효한_값으로_생성된다(self) -> None:
        snap = _valid_snapshot()
        assert snap.notional == Decimal("1100")
        assert snap.unrealized_pnl_pct == Decimal("0.1")

    @pytest.mark.parametrize(
        "field,value",
        [
            ("symbol", ""),
            ("quantity", Decimal("0")),
            ("quantity", Decimal("-1")),
            ("entry_price", Decimal("0")),
            ("current_price", Decimal("0")),
        ],
    )
    def test_불변식_위반_시_RiskDomainError(self, field: str, value) -> None:
        with pytest.raises(RiskDomainError):
            _valid_snapshot(**{field: value})


class TestRiskContext:
    def test_유효한_컨텍스트_파생값(self) -> None:
        ctx = _valid_context()
        # drawdown = (12000 - 10000) / 12000
        assert ctx.drawdown_pct == (Decimal("2000") / Decimal("12000"))
        # daily_pnl = (10000 - 11000) / 11000
        assert ctx.daily_pnl_pct == (Decimal("-1000") / Decimal("11000"))
        assert ctx.positions == ()

    def test_equity_0_이하는_거부(self) -> None:
        with pytest.raises(RiskDomainError):
            _valid_context(equity=Decimal("0"))

    def test_peak_equity_가_equity_보다_작으면_거부(self) -> None:
        with pytest.raises(RiskDomainError):
            _valid_context(peak_equity=Decimal("9000"))

    def test_candidate_쌍은_함께_제공되어야_한다(self) -> None:
        with pytest.raises(RiskDomainError):
            _valid_context(candidate_symbol="AAA", candidate_notional=None)
        with pytest.raises(RiskDomainError):
            _valid_context(candidate_symbol=None, candidate_notional=Decimal("100"))

    def test_candidate_notional_양수(self) -> None:
        with pytest.raises(RiskDomainError):
            _valid_context(
                candidate_symbol="AAA", candidate_notional=Decimal("0")
            )

    def test_candidate_정상_주입(self) -> None:
        ctx = _valid_context(
            candidate_symbol="AAA", candidate_notional=Decimal("500")
        )
        assert ctx.candidate_symbol == "AAA"
        assert ctx.candidate_notional == Decimal("500")
