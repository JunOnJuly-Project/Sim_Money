"""
ComputeTargetWeights 유스케이스 단위 테스트.

WHY: 더미 WeightingStrategy 를 주입해 유스케이스 자체 로직
     (정규화, 빈 입력 처리)만 격리 검증한다.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

import pytest

from portfolio.application.ports.weighting_strategy import SignalInput, WeightingStrategy
from portfolio.application.use_cases.compute_target_weights import ComputeTargetWeights
from portfolio.domain.constraints import PortfolioConstraints
from portfolio.domain.weight import TargetWeight


# --- 더미 전략 ---

class FixedWeightStrategy:
    """테스트용 고정 비중 반환 전략."""

    def __init__(self, result: tuple[TargetWeight, ...]) -> None:
        self._result = result

    def compute(
        self,
        signals: Sequence[SignalInput],
        constraints: PortfolioConstraints,
    ) -> tuple[TargetWeight, ...]:
        return self._result


_CONSTRAINTS = PortfolioConstraints()


# --- 테스트 ---

def test_빈_시그널_빈_결과_반환():
    strategy = FixedWeightStrategy(())
    uc = ComputeTargetWeights(strategy=strategy)
    assert uc.execute([], _CONSTRAINTS) == ()


def test_합이_1_이하면_그대로_반환():
    weights = (
        TargetWeight("A", Decimal("0.5")),
        TargetWeight("B", Decimal("0.5")),
    )
    uc = ComputeTargetWeights(strategy=FixedWeightStrategy(weights))
    result = uc.execute([SignalInput("A", Decimal("1"))], _CONSTRAINTS)
    assert result == weights


def test_합이_1_초과하면_정규화():
    """합이 1.2 이면 각 비중을 1.2 로 나눠 정규화해야 한다."""
    weights = (
        TargetWeight("A", Decimal("0.6")),
        TargetWeight("B", Decimal("0.6")),
    )
    uc = ComputeTargetWeights(strategy=FixedWeightStrategy(weights))
    result = uc.execute([], _CONSTRAINTS)
    total = sum(w.weight for w in result)
    assert abs(total - Decimal("1")) < Decimal("1e-9")


def test_정규화_후_합_보존():
    """정규화 결과의 비중 합은 항상 1이어야 한다."""
    weights = (
        TargetWeight("A", Decimal("0.4")),
        TargetWeight("B", Decimal("0.4")),
        TargetWeight("C", Decimal("0.4")),
    )
    uc = ComputeTargetWeights(strategy=FixedWeightStrategy(weights))
    result = uc.execute([], _CONSTRAINTS)
    total = sum(w.weight for w in result)
    assert abs(total - Decimal("1")) < Decimal("1e-9")


def test_정규화_결과_심볼_보존():
    """정규화 후에도 심볼 순서와 식별자가 유지되어야 한다."""
    weights = (
        TargetWeight("A", Decimal("0.4")),
        TargetWeight("B", Decimal("0.4")),
        TargetWeight("C", Decimal("0.4")),
    )
    uc = ComputeTargetWeights(strategy=FixedWeightStrategy(weights))
    result = uc.execute([], _CONSTRAINTS)
    symbols = [w.symbol for w in result]
    assert symbols == ["A", "B", "C"]


def test_epsilon_이내_합은_정규화_안함():
    """합이 1 + epsilon 이내이면 정규화하지 않는다."""
    weights = (
        TargetWeight("A", Decimal("0.5")),
        TargetWeight("B", Decimal("0.5")),
    )
    uc = ComputeTargetWeights(strategy=FixedWeightStrategy(weights))
    result = uc.execute([], _CONSTRAINTS)
    # 원래 객체와 동일해야 한다
    assert result[0].weight == Decimal("0.5")
    assert result[1].weight == Decimal("0.5")
