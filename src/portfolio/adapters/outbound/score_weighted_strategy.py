"""
ScoreWeightedStrategy 아웃바운드 어댑터.

WHY: EqualWeightStrategy 는 모든 종목을 동등하게 취급하지만,
     trading_signal 의 score 가 클수록 더 높은 비중을 부여해야
     신호 강도를 포트폴리오 구성에 반영할 수 있다.
     max_position_weight 초과분은 단순 캡으로 잘라내고 재분배하지 않는다 —
     ADR-004 의 YAGNI 원칙에 따라 재분배 로직은 요구가 생길 때 추가한다.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from portfolio.application.ports.weighting_strategy import SignalInput
from portfolio.domain.constraints import PortfolioConstraints
from portfolio.domain.weight import TargetWeight

_ZERO = Decimal("0")
_ONE = Decimal("1")


class ScoreWeightedStrategy:
    """score 비례 가중치 계산 전략.

    각 종목의 weight = (score / total_score) * investable.
    score 합이 0 이면 균등 분배로 폴백한다.
    """

    def compute(
        self,
        signals: Sequence[SignalInput],
        constraints: PortfolioConstraints,
    ) -> tuple[TargetWeight, ...]:
        """score 비례 비중을 계산하고 제약 조건을 적용한다."""
        if not signals:
            return ()
        _validate_scores(signals)

        total_score = sum(s.score for s in signals)
        investable = _ONE - constraints.cash_buffer

        weights = _compute_raw_weights(signals, total_score, investable)
        return _apply_cap(signals, weights, constraints.max_position_weight)


def _validate_scores(signals: Sequence[SignalInput]) -> None:
    """score 가 음수인 경우 ValueError 를 발생시킨다."""
    for s in signals:
        if s.score < _ZERO:
            raise ValueError("score 는 0 이상이어야 합니다")


def _compute_raw_weights(
    signals: Sequence[SignalInput],
    total_score: Decimal,
    investable: Decimal,
) -> list[Decimal]:
    """총 score 대비 비율로 원시 비중을 계산한다.

    WHY: total_score 가 0 이면 균등 분배로 폴백한다.
         모든 score 가 0 인 경우에도 합리적인 결과를 보장한다.
    """
    if total_score == _ZERO:
        equal = investable / Decimal(len(signals))
        return [equal] * len(signals)
    return [(s.score / total_score) * investable for s in signals]


def _apply_cap(
    signals: Sequence[SignalInput],
    weights: list[Decimal],
    cap: Decimal,
) -> tuple[TargetWeight, ...]:
    """max_position_weight 캡을 적용해 초과분을 단순 절삭한다.

    WHY: 재분배 없이 초과분을 버리는 단순화로 YAGNI 를 준수한다.
         절삭 후 총합이 investable 보다 낮아질 수 있으나 이는 의도된 동작이다.
    """
    return tuple(
        TargetWeight(s.symbol, min(w, cap))
        for s, w in zip(signals, weights)
    )
