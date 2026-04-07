"""
PerformanceCalculator 포트 인터페이스.

WHY: 성과 지표 계산 방식(샤프 비율, 소르티노, 칼마 등)을
     전략 패턴으로 교체 가능하게 하려면 포트 인터페이스가 필요하다.
     @runtime_checkable Protocol 로 어댑터를 동적으로 검증한다.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PerformanceCalculator(Protocol):
    """성과 지표 계산기 포트."""

    def compute(self, trades, equity_curve):
        """거래 목록과 자본 곡선을 받아 성과 지표를 계산한다."""
        ...
