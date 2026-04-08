"""RiskDecision 값 객체 테스트 (M5 S1)."""

import pytest

from risk.domain import Allow, BlockNew, ForceClose, RiskDomainError


class TestRiskDecision:
    def test_severity_순서는_Allow_lt_BlockNew_lt_ForceClose(self) -> None:
        assert Allow().severity < BlockNew("x").severity
        assert BlockNew("x").severity < ForceClose("AAA", "stop").severity

    def test_BlockNew_reason_필수(self) -> None:
        with pytest.raises(RiskDomainError):
            BlockNew(reason="")

    def test_ForceClose_symbol_reason_필수(self) -> None:
        with pytest.raises(RiskDomainError):
            ForceClose(symbol="", reason="x")
        with pytest.raises(RiskDomainError):
            ForceClose(symbol="AAA", reason="")

    def test_Allow_는_기본_reason_허용(self) -> None:
        assert Allow().reason == ""
