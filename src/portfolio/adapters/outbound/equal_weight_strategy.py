"""
EqualWeightStrategy 아웃바운드 어댑터.

WHY: 균등 비중은 가장 단순한 기준선(baseline) 전략이다.
     max_position_weight 캡 초과 종목을 캡으로 잘라내고
     잔여 비중을 나머지 종목에 1회 재분배해 제약을 준수한다.
     (반복 재분배는 L1 에서 불필요하며 복잡성만 증가시킨다.)
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from portfolio.application.ports.weighting_strategy import SignalInput
from portfolio.domain.constraints import PortfolioConstraints
from portfolio.domain.weight import TargetWeight

_ZERO = Decimal("0")
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
        return _apply_max_cap(signals, base_weight, constraints.max_position_weight, investable)


def _apply_max_cap(
    signals: Sequence[SignalInput],
    base_weight: Decimal,
    max_cap: Decimal,
    investable: Decimal,
) -> tuple[TargetWeight, ...]:
    """max_position_weight 초과 종목은 캡으로 잘라내고 잔여를 재분배한다."""
    if base_weight <= max_cap:
        # WHY: 캡 미달이면 재분배 없이 바로 반환해 계산 비용을 줄인다
        return tuple(TargetWeight(s.symbol, base_weight) for s in signals)

    capped_count = len(signals)
    capped_weight = max_cap
    uncapped_symbols = []
    excess = _ZERO

    for sig in signals:
        if base_weight > max_cap:
            excess += base_weight - max_cap
        else:
            uncapped_symbols.append(sig.symbol)

    # 캡 초과가 모든 종목이므로 uncapped 는 없음; 잔여를 균등 재분배
    if not uncapped_symbols:
        return tuple(TargetWeight(s.symbol, max_cap) for s in signals)

    redistributed = excess / Decimal(len(uncapped_symbols))
    result: list[TargetWeight] = []
    for sig in signals:
        if sig.symbol in uncapped_symbols:
            weight = min(base_weight + redistributed, max_cap)
        else:
            weight = capped_weight
        result.append(TargetWeight(sig.symbol, weight))
    return tuple(result)
