"""
SignalSource 포트 인터페이스.

WHY: 신호 생성 로직을 전략 패턴으로 교체 가능하게 하려면
     포트 인터페이스가 필요하다. @runtime_checkable Protocol 로
     다양한 전략 구현체를 동적으로 검증할 수 있다.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SignalSource(Protocol):
    """매매 신호 생성기 포트."""

    def generate(self, price_history):
        """시장 데이터를 받아 매매 신호 목록을 생성한다."""
        ...
