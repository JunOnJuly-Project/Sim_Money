"""RiskWeightCapValidator 단위 테스트 (M5 S11).

WHY: portfolio 캡 검사 로직이 risk.PositionLimitGuard 위임으로 동작해도
     기존 인라인 의미와 동일해야 한다. 경계값과 PlanRebalance 통합을 함께 검증.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from portfolio.adapters.outbound.risk_weight_cap_validator import RiskWeightCapValidator
from portfolio.application.use_cases.plan_rebalance import PlanRebalance
from portfolio.domain.constraints import PortfolioConstraints
from portfolio.domain.errors import ConstraintViolation
from portfolio.domain.weight import TargetWeight


class TestRiskWeightCapValidator_단위:
    def test_캡_이내는_통과한다(self) -> None:
        validator = RiskWeightCapValidator()
        targets = [
            TargetWeight(symbol="A", weight=Decimal("0.3")),
            TargetWeight(symbol="B", weight=Decimal("0.4")),
        ]
        validator.validate(targets, Decimal("0.5"))  # 예외 없음

    def test_캡_경계값_정확히_같으면_통과한다(self) -> None:
        validator = RiskWeightCapValidator()
        targets = [TargetWeight(symbol="A", weight=Decimal("0.5"))]
        validator.validate(targets, Decimal("0.5"))  # 예외 없음

    def test_캡_초과는_ConstraintViolation을_발생시킨다(self) -> None:
        validator = RiskWeightCapValidator()
        targets = [TargetWeight(symbol="A", weight=Decimal("0.6"))]
        with pytest.raises(ConstraintViolation, match="max_position_weight"):
            validator.validate(targets, Decimal("0.5"))

    def test_가중치_0인_타깃은_건너뛴다(self) -> None:
        # WHY: PositionLimitGuard 는 양수 notional 만 받으므로 0 비중은 스킵해야 한다.
        validator = RiskWeightCapValidator()
        targets = [
            TargetWeight(symbol="A", weight=Decimal("0")),
            TargetWeight(symbol="B", weight=Decimal("0.4")),
        ]
        validator.validate(targets, Decimal("0.5"))  # 예외 없음


class TestPlanRebalance_validator_주입:
    """PlanRebalance 에 validator 를 주입했을 때 동일하게 동작해야 한다."""

    def test_validator_주입시_초과는_차단된다(self) -> None:
        constraints = PortfolioConstraints(max_position_weight=Decimal("0.3"))
        plan = PlanRebalance(
            constraints=constraints,
            weight_cap_validator=RiskWeightCapValidator(),
        )
        targets = [TargetWeight(symbol="A", weight=Decimal("0.5"))]

        with pytest.raises(ConstraintViolation, match="max_position_weight"):
            plan.execute(current=[], targets=targets, total_equity=Decimal("10000"))

    def test_validator_주입시_캡_이내는_정상_플랜을_만든다(self) -> None:
        constraints = PortfolioConstraints(max_position_weight=Decimal("0.5"))
        plan = PlanRebalance(
            constraints=constraints,
            weight_cap_validator=RiskWeightCapValidator(),
        )
        targets = [TargetWeight(symbol="A", weight=Decimal("0.4"))]

        result = plan.execute(current=[], targets=targets, total_equity=Decimal("10000"))
        assert len(result.intents) == 1
        assert result.intents[0].symbol == "A"
