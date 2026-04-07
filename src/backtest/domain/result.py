"""
백테스트 실행 결과 값 객체.

WHY: 백테스트 결과는 생성 후 절대 변경되어서는 안 된다.
     컬렉션도 tuple 로 강제해 외부에서 리스트를 넘겨도 불변 컬렉션으로
     저장되도록 __post_init__ 에서 변환한다.
     object.__setattr__ 을 사용하는 이유는 frozen=True 가 적용된 상태에서
     합법적으로 필드를 초기화할 수 있는 유일한 방법이기 때문이다.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backtest.domain.metrics import PerformanceMetrics
from backtest.domain.trade import Trade


@dataclass(frozen=True)
class BacktestResult:
    """백테스트 실행 결과 값 객체."""

    trades: tuple[Trade, ...]
    equity_curve: tuple[tuple, ...]
    metrics: PerformanceMetrics

    def __post_init__(self) -> None:
        """컬렉션 타입을 tuple 로 강제 변환한다."""
        object.__setattr__(self, "trades", tuple(self.trades))
        object.__setattr__(self, "equity_curve", tuple(self.equity_curve))
