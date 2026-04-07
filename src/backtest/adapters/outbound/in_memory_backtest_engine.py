"""
인메모리 백테스트 엔진 어댑터.

WHY: TradeExecutor + PerformanceCalculator 기본 구현체를 조립해
     외부 의존성 없이 바로 사용 가능한 엔진을 제공한다.
     DI 컨테이너 없이도 기본 생성이 가능하여 테스트와 스크립트에서 간편하게 활용한다.
"""
from __future__ import annotations

from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor
from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator
from backtest.application.use_cases.run_backtest import RunBacktest
from backtest.domain.backtest_config import BacktestConfig


class InMemoryBacktestEngine:
    """기본 어댑터를 조립한 인메모리 백테스트 엔진."""

    def __init__(
        self,
        trade_executor: InMemoryTradeExecutor | None = None,
        performance_calculator: RatioPerformanceCalculator | None = None,
    ) -> None:
        """기본 구현체를 주입하거나 외부에서 교체 가능하게 초기화한다."""
        self._use_case = RunBacktest(
            trade_executor or InMemoryTradeExecutor(),
            performance_calculator or RatioPerformanceCalculator(),
        )

    def run(
        self,
        signals,
        price_history,
        config: BacktestConfig | None = None,
    ):
        """신호·가격 이력·설정으로 백테스트를 실행하고 결과를 반환한다."""
        if config is None:
            # WHY: config 없이 실행하는 것은 미구현 경로이다.
            #      S3 스켈레톤 테스트 계약과 호환성을 유지한다.
            raise NotImplementedError("M2 S4: config 인자가 필요합니다.")
        return self._use_case.execute(signals, price_history, config)
