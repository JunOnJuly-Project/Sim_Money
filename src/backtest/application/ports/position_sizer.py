"""
PositionSizer 포트 인터페이스.

WHY: 포지션 사이징 방식(strength 직접 사용, portfolio 기반, 리스크 기반 등)을
     전략 패턴으로 교체 가능하게 하려면 포트 인터페이스가 필요하다.
     Protocol 로 정의해 다양한 구현체를 런타임에 교체할 수 있다.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from backtest.domain.signal import Signal


@runtime_checkable
class PositionSizer(Protocol):
    """signal + available_cash → 투자 비율(0~1) 결정 포트."""

    def size(self, signal: Signal, available_cash: Decimal) -> Decimal:
        """신호와 가용 현금을 받아 투자할 자산 비율(0~1)을 반환한다."""
        ...
