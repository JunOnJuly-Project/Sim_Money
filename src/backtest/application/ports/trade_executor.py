"""
TradeExecutor 포트 인터페이스.

WHY: 주문 실행 방식(현재가 체결, 슬리피지 모델, 실거래 API 등)을
     전략 패턴으로 교체 가능하게 하려면 포트 인터페이스가 필요하다.
     @runtime_checkable Protocol 로 어댑터를 동적으로 검증한다.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TradeExecutor(Protocol):
    """주문 실행기 포트."""

    def execute(self, signal, position):
        """신호와 현재 포지션 정보를 받아 거래를 실행한다."""
        ...
