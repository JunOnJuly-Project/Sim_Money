"""
CurrentPosition 값 객체.

WHY: 현재 보유 포지션은 생성 이후 변경되어서는 안 된다.
     수량 음수 불변식을 생성 시점에 검증해 잘못된 포지션이
     리밸런싱 계산에 오염되는 것을 방지한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

_QUANTITY_MIN = Decimal("0")


@dataclass(frozen=True)
class CurrentPosition:
    """단일 보유 포지션 값 객체."""

    symbol: str
    quantity: Decimal
    market_value: Decimal

    def __post_init__(self) -> None:
        """불변식 검증: symbol 비공백, quantity ≥ 0."""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol 은 비공백 문자열이어야 합니다.")
        if self.quantity < _QUANTITY_MIN:
            raise ValueError(
                f"quantity 는 {_QUANTITY_MIN} 이상이어야 합니다. "
                f"실제값: {self.quantity}"
            )
