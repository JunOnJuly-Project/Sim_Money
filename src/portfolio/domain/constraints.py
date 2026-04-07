"""
PortfolioConstraints 값 객체.

WHY: 제약 조건은 유스케이스 실행 중 변경되어서는 안 된다.
     max_position_weight 와 cash_buffer 의 0~1 범위 불변식을
     생성 시점에 검증해 잘못된 제약이 사이징 계산에 오염되는 것을 방지한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

_CONSTRAINT_MIN = Decimal("0")
_CONSTRAINT_MAX = Decimal("1")


@dataclass(frozen=True)
class PortfolioConstraints:
    """포트폴리오 제약 조건 값 객체."""

    max_position_weight: Decimal = field(default_factory=lambda: Decimal("1"))
    cash_buffer: Decimal = field(default_factory=lambda: Decimal("0"))
    long_only: bool = True

    def __post_init__(self) -> None:
        """불변식 검증: max_position_weight, cash_buffer 는 0~1 범위."""
        _validate_rate("max_position_weight", self.max_position_weight)
        _validate_rate("cash_buffer", self.cash_buffer)


def _validate_rate(name: str, value: Decimal) -> None:
    """비율 값이 0 이상 1 이하인지 검증한다."""
    if not (_CONSTRAINT_MIN <= value <= _CONSTRAINT_MAX):
        raise ValueError(
            f"{name} 은 {_CONSTRAINT_MIN} 이상 {_CONSTRAINT_MAX} 이하여야 합니다. "
            f"실제값: {value}"
        )
