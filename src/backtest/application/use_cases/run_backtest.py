"""
RunBacktest 유스케이스.

WHY: 백테스트 실행 흐름(신호 소비 → 거래 실행 → 성과 계산)을 하나의 유스케이스로
     캡슐화하고, 포트 인터페이스에만 의존해 어댑터 구현을 런타임에 교체 가능하게 한다.
     M2 S4에서는 시그니처만 정의하고 구현은 다음 슬라이스에서 추가한다.
"""
from __future__ import annotations

from typing import Sequence

from backtest.application.ports.performance_calculator import PerformanceCalculator
from backtest.application.ports.trade_executor import TradeExecutor
from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.result import BacktestResult
from backtest.domain.signal import Signal


class RunBacktest:
    """백테스트 실행 유스케이스."""

    def __init__(
        self,
        trade_executor: TradeExecutor,
        performance_calculator: PerformanceCalculator,
    ) -> None:
        """포트 구현체를 주입받아 유스케이스를 초기화한다."""
        self._trade_executor = trade_executor
        self._performance_calculator = performance_calculator

    def execute(
        self,
        signals: Sequence[Signal],
        price_history: dict,
        config: BacktestConfig,
    ) -> BacktestResult:
        """신호·가격 이력·설정을 받아 백테스트를 실행하고 결과를 반환한다."""
        raise NotImplementedError("M2 S4: RED 테스트를 위한 시그니처만")
