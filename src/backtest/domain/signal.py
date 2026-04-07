"""
매매 신호 값 객체 및 방향 열거형.

WHY: 신호는 생성 후 변경되면 백테스트 재현성이 깨진다.
     frozen dataclass 로 불변성을 보장하고 strength 를 [0, 1] 범위로
     강제해 하위 계산 컴포넌트에서 음수·초과 강도가 오류를 유발하지 않도록 한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Side(Enum):
    """매매 방향 — 매수(LONG), 매도(SHORT), 청산(EXIT) 세 방향만 허용."""

    LONG = "LONG"
    SHORT = "SHORT"
    EXIT = "EXIT"


@dataclass(frozen=True)
class Signal:
    """단일 매매 신호 값 객체."""

    timestamp: datetime
    ticker: str
    side: Side
    strength: float

    def __post_init__(self) -> None:
        """신호 불변식 검증."""
        if not self.ticker:
            raise ValueError("ticker 는 빈 문자열일 수 없습니다.")
        if self.strength < 0.0:
            raise ValueError("strength 는 0.0 이상이어야 합니다.")
        if self.strength > 1.0:
            raise ValueError("strength 는 1.0 이하여야 합니다.")
