"""
인메모리 백테스트 엔진 어댑터.

WHY: TradeExecutor + PerformanceCalculator + PositionSizer 기본 구현체를 조립해
     외부 의존성 없이 바로 사용 가능한 엔진을 제공한다.
     DI 컨테이너 없이도 기본 생성이 가능하여 테스트와 스크립트에서 간편하게 활용한다.

사이저 위치 변경:
     M3 S13 부터 PositionSizer 는 InMemoryTradeExecutor 가 아닌
     RunBacktest 유스케이스에 주입된다. InMemoryBacktestEngine 도 sizer 를
     직접 받아 RunBacktest 에 전달하도록 변경한다.
"""
from __future__ import annotations

from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor
from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator
from backtest.adapters.outbound.strength_position_sizer import StrengthPositionSizer
from backtest.application.ports.entry_filter import EntryFilter
from backtest.application.ports.position_sizer import PositionSizer
from backtest.application.use_cases.run_backtest import RunBacktest
from backtest.domain.backtest_config import BacktestConfig


class InMemoryBacktestEngine:
    """기본 어댑터를 조립한 인메모리 백테스트 엔진."""

    def __init__(
        self,
        trade_executor: InMemoryTradeExecutor | None = None,
        performance_calculator: RatioPerformanceCalculator | None = None,
        sizer: PositionSizer | None = None,
        entry_filter: EntryFilter | None = None,
    ) -> None:
        """기본 구현체를 주입하거나 외부에서 교체 가능하게 초기화한다.

        WHY: sizer 를 직접 받아 RunBacktest 에 전달한다.
             None 이면 RunBacktest 기본값(StrengthPositionSizer)을 사용한다.
             performance_calculator 는 run() 호출 시 config.risk_free_rate 를 읽어
             생성하므로 None 으로 받아 지연 초기화한다.
        """
        self._trade_executor = trade_executor or InMemoryTradeExecutor()
        # WHY: 외부에서 calculator 를 직접 주입하면 rfr 주입 없이 그대로 사용한다.
        #      None 이면 run() 에서 config.risk_free_rate 를 반영해 생성한다.
        self._performance_calculator = performance_calculator
        self._sizer = sizer
        self._entry_filter = entry_filter

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

        # WHY: 외부 주입 calculator 가 없을 때만 config.risk_free_rate 를 읽어
        #      RatioPerformanceCalculator 를 생성한다. 주입된 calculator 는 그대로 사용해
        #      단위 테스트에서 Fake 주입이 깨지지 않게 한다.
        calculator = self._performance_calculator or RatioPerformanceCalculator(
            risk_free_rate=float(config.risk_free_rate)
        )

        use_case = RunBacktest(
            self._trade_executor, calculator, self._sizer, self._entry_filter,
        )
        return use_case.execute(signals, price_history, config)
