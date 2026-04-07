"""
EqualWeightStrategy 아웃바운드 어댑터.

WHY: 균등 비중은 가장 단순한 기준선(baseline) 전략이다.
     모든 종목이 동일한 base_weight 를 갖기 때문에
     max_position_weight 초과 시 전 종목이 동시에 캡에 묶인다.
     (score 차등이 없는 균등 전략 특성상 "일부는 캡, 나머지 재분배" 분기는
      이론적으로 도달할 수 없어 제거했다 — YAGNI.)
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from portfolio.application.ports.weighting_strategy import SignalInput
from portfolio.domain.constraints import PortfolioConstraints
from portfolio.domain.weight import TargetWeight

_ONE = Decimal("1")


class EqualWeightStrategy:
    """균등 비중 가중치 계산 전략."""

    def compute(
        self,
        signals: Sequence[SignalInput],
        constraints: PortfolioConstraints,
    ) -> tuple[TargetWeight, ...]:
        """시그널 수에 따라 균등 비중을 계산하고 제약 조건을 적용한다."""
        if not signals:
            return ()
        investable = _ONE - constraints.cash_buffer
        base_weight = investable / Decimal(len(signals))
        final_weight = min(base_weight, constraints.max_position_weight)
        return tuple(TargetWeight(s.symbol, final_weight) for s in signals)
