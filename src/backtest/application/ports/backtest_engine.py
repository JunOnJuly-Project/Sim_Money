"""
BacktestEngine 포트 인터페이스.

WHY: DIP — 애플리케이션이 구체적 엔진 구현에 의존하지 않도록
     @runtime_checkable Protocol 로 계약을 정의한다.
     런타임 isinstance 검사가 가능해야 어댑터 등록 및 검증 로직을 구현할 수 있다.
"""
from __future__ import annotations

from typing import Mapping, Protocol, Sequence, runtime_checkable

from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.price_bar import PriceBar
from backtest.domain.result import BacktestResult
from backtest.domain.signal import Signal


@runtime_checkable
class BacktestEngine(Protocol):
    """백테스트 실행 엔진 포트."""

    def run(
        self,
        signals: Sequence[Signal],
        price_history: Mapping[str, Sequence[PriceBar]],
        config: BacktestConfig,
    ) -> BacktestResult:
        """신호·가격 이력·설정을 받아 백테스트를 실행하고 결과를 반환한다."""
        ...
