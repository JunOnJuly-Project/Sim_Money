"""
PortfolioPositionSizer 어댑터.

WHY: portfolio.WeightingStrategy 를 백테스트 사이징에 연결한다.
     단일 signal 을 SignalInput 으로 변환해 전략에 전달하고
     첫 TargetWeight.weight 를 투자 비율로 반환한다.
     이 어댑터는 backtest.adapters.outbound 레이어에만 존재해
     백테스트 도메인을 portfolio 에 오염시키지 않는다.
"""
from __future__ import annotations

from decimal import Decimal

from portfolio.application.ports.weighting_strategy import SignalInput, WeightingStrategy
from portfolio.domain.constraints import PortfolioConstraints

from backtest.domain.signal import Signal

_ZERO = Decimal("0")


class PortfolioPositionSizer:
    """WeightingStrategy 를 이용해 단일 signal 의 투자 비율을 결정하는 사이저."""

    def __init__(
        self,
        strategy: WeightingStrategy,
        constraints: PortfolioConstraints,
    ) -> None:
        """전략과 제약 조건을 주입받아 초기화한다."""
        self._strategy = strategy
        self._constraints = constraints

    def size(self, signal: Signal, available_cash: Decimal) -> Decimal:
        """signal 하나를 SignalInput 으로 변환해 전략의 목표 비중을 반환한다.

        WHY: 단일 신호 진입 시에도 portfolio 제약(cash_buffer, max_position_weight)을
             일관되게 적용하기 위해 전략을 그대로 활용한다.
             전략이 빈 결과를 반환하면 0 을 반환해 안전하게 처리한다.
        """
        signal_input = SignalInput(symbol=signal.ticker, score=signal.strength)
        weights = self._strategy.compute([signal_input], self._constraints)
        if not weights:
            return _ZERO
        return weights[0].weight
