"""
ComputeTargetWeights 유스케이스.

WHY: 전략 호출 결과의 합이 부동소수점 오차로 1을 미세하게 벗어날 수 있다.
     epsilon 검증 후 정규화를 유스케이스가 책임짐으로써 어댑터는
     "합이 정확히 1이어야 한다"는 내부 불변식을 신경쓰지 않아도 된다.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from portfolio.application.ports.weighting_strategy import (
    SignalInput,
    WeightingStrategy,
)
from portfolio.domain.constraints import PortfolioConstraints
from portfolio.domain.weight import TargetWeight

_WEIGHT_SUM_EPSILON = Decimal("1e-9")
_ONE = Decimal("1")
_ZERO = Decimal("0")


@dataclass(frozen=True)
class ComputeTargetWeights:
    """목표 비중 계산 유스케이스."""

    strategy: WeightingStrategy

    def execute(
        self,
        signals: Sequence[SignalInput],
        constraints: PortfolioConstraints,
    ) -> tuple[TargetWeight, ...]:
        """시그널과 제약 조건을 받아 정규화된 목표 비중 튜플을 반환한다."""
        weights = self.strategy.compute(signals, constraints)
        if not weights:
            return weights
        return _normalize_if_needed(weights)


def _normalize_if_needed(
    weights: tuple[TargetWeight, ...],
) -> tuple[TargetWeight, ...]:
    """합이 1을 초과하면 정규화, epsilon 이내이면 그대로 반환한다."""
    total = sum((w.weight for w in weights), _ZERO)
    if total <= _ONE + _WEIGHT_SUM_EPSILON:
        return weights
    # WHY: 전략이 cap/buffer 잔여분을 재분배하지 않은 경우 유스케이스가 1회 보정한다
    return tuple(
        TargetWeight(symbol=w.symbol, weight=w.weight / total) for w in weights
    )
