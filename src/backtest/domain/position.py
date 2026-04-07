"""
보유 포지션 값 객체.

WHY: 포지션 진입 정보는 사후 변경되어서는 안 된다.
     진입가와 수량의 양수 불변식을 생성 시점에 검증해
     잘못된 포지션이 손익 계산에 오염되는 것을 방지한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Position:
    """단일 보유 포지션 값 객체."""

    ticker: str
    quantity: Decimal
    entry_price: Decimal
    entry_time: datetime

    def __post_init__(self) -> None:
        """포지션 불변식 검증."""
        if self.quantity <= Decimal("0"):
            raise ValueError("quantity 는 0 보다 커야 합니다.")
        if self.entry_price <= Decimal("0"):
            raise ValueError("entry_price 는 0 보다 커야 합니다.")
