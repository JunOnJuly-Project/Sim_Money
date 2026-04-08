"""
PortfolioPositionSizer 어댑터.

WHY: portfolio.WeightingStrategy 를 백테스트 사이징에 연결한다.
     size_group 으로 동일 타임스탬프 신호 전체를 한 번에 전달해
     EqualWeightStrategy/ScoreWeightedStrategy 가 포트폴리오 관점으로 동작하게 한다.
     이 어댑터는 backtest.adapters.outbound 레이어에만 존재해
     백테스트 도메인을 portfolio 에 오염시키지 않는다.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from portfolio.application.ports.weighting_strategy import SignalInput, WeightingStrategy
from portfolio.domain.constraints import PortfolioConstraints

from backtest.domain.signal import Signal

_ZERO = Decimal("0")


class PortfolioPositionSizer:
    """WeightingStrategy 를 이용해 신호 그룹의 투자 비율을 결정하는 사이저."""

    def __init__(
        self,
        strategy: WeightingStrategy,
        constraints: PortfolioConstraints,
    ) -> None:
        """전략과 제약 조건을 주입받아 초기화한다."""
        self._strategy = strategy
        self._constraints = constraints

    def size_group(
        self,
        signals: Sequence[Signal],
        available_cash: Decimal,
    ) -> Sequence[Decimal]:
        """신호 그룹 전체를 한 번에 전략에 전달해 각 신호의 투자 비율을 반환한다.

        WHY: 형제 신호를 모두 인지해야 EqualWeight/ScoreWeighted 등
             포트폴리오 제약(cash_buffer, max_position_weight)이 올바르게 적용된다.
             단일 신호 반복 호출로는 전체 비중 합산 제어가 불가능하다.
             반환 순서는 입력 signals 의 순서를 보장한다.
        """
        if not signals:
            return []

        symbol_to_index = {s.ticker: i for i, s in enumerate(signals)}
        inputs = [SignalInput(symbol=s.ticker, score=s.strength) for s in signals]
        computed = self._strategy.compute(inputs, self._constraints)

        weights: list[Decimal] = [_ZERO] * len(signals)
        for target in computed:
            idx = symbol_to_index.get(target.symbol)
            if idx is not None:
                weights[idx] = target.weight
        return weights

    def size(self, signal: Signal, available_cash: Decimal) -> Decimal:
        """단일 신호의 투자 비율을 반환한다 (size_group 위임).

        WHY: 단일 신호도 size_group 을 통해 처리해 코드 중복을 제거한다.
             단일 신호 진입 시에도 portfolio 제약이 일관되게 적용된다.
        """
        return self.size_group([signal], available_cash)[0]
