"""
TargetWeight 값 객체.

WHY: 목표 비중은 생성 이후 변경되어서는 안 된다.
     symbol 비공백·weight 범위 불변식을 생성 시점에 검증해
     잘못된 비중이 유스케이스에 오염되는 것을 방지한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

_WEIGHT_MIN = Decimal("0")
_WEIGHT_MAX = Decimal("1")


@dataclass(frozen=True)
class TargetWeight:
    """단일 종목의 목표 비중 값 객체."""

    symbol: str
    weight: Decimal

    def __post_init__(self) -> None:
        """불변식 검증: symbol 비공백, 0 ≤ weight ≤ 1."""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol 은 비공백 문자열이어야 합니다.")
        if not (_WEIGHT_MIN <= self.weight <= _WEIGHT_MAX):
            raise ValueError(
                f"weight 는 {_WEIGHT_MIN} 이상 {_WEIGHT_MAX} 이하여야 합니다. "
                f"실제값: {self.weight}"
            )
