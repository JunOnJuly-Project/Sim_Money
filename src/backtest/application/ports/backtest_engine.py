"""
BacktestEngine 포트 인터페이스.

WHY: DIP — 애플리케이션이 구체적 엔진 구현에 의존하지 않도록
     @runtime_checkable Protocol 로 계약을 정의한다.
     런타임 isinstance 검사가 가능해야 어댑터 등록 및 검증 로직을 구현할 수 있다.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BacktestEngine(Protocol):
    """백테스트 실행 엔진 포트."""

    def run(self, signals, price_history):
        """신호와 가격 이력을 받아 백테스트를 실행하고 결과를 반환한다."""
        ...
