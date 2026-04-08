"""
백테스트 성과 지표 값 객체.

WHY: 성과 지표는 집계 완료 후 고정되어야 재현성이 보장된다.
     승률 [0, 1] 범위와 최대낙폭 비양수 불변식을 생성 시점에 검증해
     논리적으로 불가능한 지표가 리포트에 표시되는 것을 방지한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PerformanceMetrics:
    """백테스트 종합 성과 지표 값 객체."""

    total_return: Decimal
    sharpe: float
    max_drawdown: Decimal
    win_rate: float
    # WHY: Sortino 는 하방 변동성만 처벌하는 risk-adjusted return, Calmar 는
    #      연율화 수익률 대비 MDD 비율로 꼬리 리스크를 요약한다. 기본값 0.0
    #      으로 기존 호출부 호환성을 유지한다.
    sortino: float = 0.0
    calmar: float = 0.0

    def __post_init__(self) -> None:
        """성과 지표 불변식 검증."""
        if self.win_rate < 0.0:
            raise ValueError("win_rate 는 0.0 이상이어야 합니다.")
        if self.win_rate > 1.0:
            raise ValueError("win_rate 는 1.0 이하여야 합니다.")
        if self.max_drawdown > Decimal("0"):
            raise ValueError("max_drawdown 은 0 이하여야 합니다.")
