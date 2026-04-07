"""
TradingSignal 값 객체.

WHY: backtest.domain.Signal 과 필드 스키마를 일치시키되 import 를 분리한다.
     동일 스키마를 유지하면 어댑터에서 1:1 변환이 가능해
     L3 간 결합 없이 backtest 파이프라인에 연결할 수 있다.
     strength 는 [0, 1] 범위를 강제해 하위 컴포넌트가
     음수·초과 강도로 인한 오동작을 유발하지 않도록 한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_signal.domain.side import Side


@dataclass(frozen=True)
class TradingSignal:
    """단일 매매 신호 불변 값 객체."""

    timestamp: datetime
    ticker: str
    side: Side
    strength: Decimal

    def __post_init__(self) -> None:
        """신호 불변식 검증."""
        if not self.ticker:
            raise ValueError("ticker 는 빈 문자열일 수 없습니다.")
        if self.strength < Decimal("0"):
            raise ValueError("strength 는 0.0 이상이어야 합니다.")
        if self.strength > Decimal("1"):
            raise ValueError("strength 는 1.0 이하여야 합니다.")
