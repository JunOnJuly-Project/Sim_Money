"""
RebalancePlan 및 OrderIntent 값 객체.

WHY: 리밸런싱 계획은 생성 이후 변경되어서는 안 된다.
     OrderIntent 는 delta_weight 부호로 매수/매도 방향을 명시하며
     side 불변식을 생성 시점에 검증해 방향 불일치를 사전에 차단한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

_SELL_SIDE: Literal["SELL"] = "SELL"
_BUY_SIDE: Literal["BUY"] = "BUY"


@dataclass(frozen=True)
class OrderIntent:
    """단일 종목의 리밸런싱 주문 의도 값 객체."""

    symbol: str
    delta_weight: Decimal
    side: Literal["BUY", "SELL"]

    def __post_init__(self) -> None:
        """불변식 검증: side 와 delta_weight 부호 일치."""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol 은 비공백 문자열이어야 합니다.")
        if self.side == _BUY_SIDE and self.delta_weight <= Decimal("0"):
            raise ValueError("BUY 주문의 delta_weight 는 양수여야 합니다.")
        if self.side == _SELL_SIDE and self.delta_weight >= Decimal("0"):
            raise ValueError("SELL 주문의 delta_weight 는 음수여야 합니다.")


@dataclass(frozen=True)
class RebalancePlan:
    """리밸런싱 주문 의도 집합 값 객체."""

    intents: tuple[OrderIntent, ...]
