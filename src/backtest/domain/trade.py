"""
완결된 거래 값 객체.

WHY: 거래 기록은 감사 추적(audit trail)의 핵심이므로 생성 후 절대 변경되어서는 안 된다.
     시간 순서(exit >= entry), 양수 가격/수량 불변식을 생성 시점에 검증해
     잘못된 거래가 성과 지표 계산에 오염되는 것을 방지한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Trade:
    """완결된 단일 거래 값 객체."""

    ticker: str
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    pnl: Decimal

    def __post_init__(self) -> None:
        """거래 불변식 검증."""
        if self.exit_time < self.entry_time:
            raise ValueError("exit_time 은 entry_time 보다 이후여야 합니다.")
        if self.quantity <= Decimal("0"):
            raise ValueError("quantity 는 0 보다 커야 합니다.")
        if self.entry_price <= Decimal("0"):
            raise ValueError("entry_price 는 0 보다 커야 합니다.")
        if self.exit_price <= Decimal("0"):
            raise ValueError("exit_price 는 0 보다 커야 합니다.")
