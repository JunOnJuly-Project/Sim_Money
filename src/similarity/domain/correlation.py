"""
Correlation 값 객체 (Value Object).

WHY: 상관계수는 [-1, 1] 범위와 최소 관측 수라는 불변식을 가진 도메인 개념이다.
     단순 float 대신 값 객체로 감싸면 불변식 위반이 생성 시점에 즉시 탐지된다.
     frozen=True 로 불변성을 보장해 공유 시 사이드 이펙트를 제거한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# 부동소수점 연산 오차 허용 범위.
# WHY: np.corrcoef 등 수치 연산은 완전 상관 데이터에서 1.0 + 2e-16 수준 오차를 낼 수 있다.
#      그러나 1e-8 이상의 초과값은 계산 오류로 간주해 차단한다.
_EPSILON: float = 1e-9

# 상관계수 계산에 필요한 최소 관측 수.
# WHY: Pearson 공식 분모(표준편차)는 n >= 2 일 때만 정의된다(자유도 = n - 1 >= 1).
_MIN_OBSERVATIONS: int = 2


@dataclass(frozen=True)
class Correlation:
    """상관계수를 표현하는 불변 값 객체.

    WHY: 도메인 계층에서 float 를 직접 사용하면 범위 검사가 흩어져
         불변식 위반 시 원인 추적이 어렵다. 값 객체로 중앙화한다.

    Attributes:
        value: 상관계수 [-1.0, 1.0]
        n: 계산에 사용된 관측 수 (>= 2)
    """

    value: float
    n: int

    def __post_init__(self) -> None:
        """생성 시 불변식을 검증한다."""
        self._validate_finite()
        self._validate_range()
        self._validate_observations()

    def _validate_finite(self) -> None:
        """WHY: NaN/Inf 가 값 객체로 유입되면 이후 모든 계산이 무음 오류를 낸다."""
        if not math.isfinite(self.value):
            raise ValueError(f"상관계수는 유한한 값이어야 합니다: {self.value!r}")

    def _validate_range(self) -> None:
        """WHY: 수학적으로 |ρ| > 1 은 불가능하다. _EPSILON 허용 범위를 초과하면 차단한다."""
        if self.value < -1.0 - _EPSILON or self.value > 1.0 + _EPSILON:
            raise ValueError(
                f"상관계수는 [-1, 1] 범위여야 합니다: {self.value!r}"
            )

    def _validate_observations(self) -> None:
        """WHY: n < 2 이면 분산 자체가 정의되지 않는다."""
        if self.n < _MIN_OBSERVATIONS:
            raise ValueError(
                f"관측 수는 {_MIN_OBSERVATIONS} 이상이어야 합니다: {self.n!r}"
            )

    def sign(self) -> int:
        """상관 방향을 반환한다.

        Returns:
            양상관이면 1, 음상관이면 -1, 무상관이면 0
        """
        if self.value > 0:
            return 1
        if self.value < 0:
            return -1
        return 0
