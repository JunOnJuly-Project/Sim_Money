"""WeightCapValidator 포트 — 목표 비중 캡 검증 (M5 S11).

WHY: PlanRebalance 가 max_position_weight 위반을 검사하는 로직을
     도메인 외부에서 교체 가능하게 만든다. 기본 인라인 검사 외에
     risk.PositionLimitGuard 를 재사용하는 어댑터를 주입할 수 있도록
     포트로 추상화한다 (ADR-005: L3↔L3 수평 의존은 어댑터에서만).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, Sequence

from portfolio.domain.weight import TargetWeight


class WeightCapValidator(Protocol):
    """목표 비중이 단일 종목 한도를 초과하는지 검증한다."""

    def validate(
        self,
        targets: Sequence[TargetWeight],
        max_position_weight: Decimal,
    ) -> None:
        """위반 시 portfolio.domain.errors.ConstraintViolation 을 발생시킨다."""
        ...
