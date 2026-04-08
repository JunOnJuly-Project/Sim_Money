"""
PositionSizer 포트 인터페이스.

WHY: 포지션 사이징 방식(strength 직접 사용, portfolio 기반, 리스크 기반 등)을
     전략 패턴으로 교체 가능하게 하려면 포트 인터페이스가 필요하다.
     Protocol 로 정의해 다양한 구현체를 런타임에 교체할 수 있다.

size_group 추가 이유:
     단일 신호 기반 size() 는 형제 신호를 인지하지 못해
     EqualWeightStrategy 등 포트폴리오 관점 전략이 제대로 작동하지 않는다.
     같은 타임스탬프 신호를 일괄 처리하는 size_group 으로 이 문제를 해결한다.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol, Sequence, runtime_checkable

from backtest.domain.signal import Signal


@runtime_checkable
class PositionSizer(Protocol):
    """signal + available_cash → 투자 비율(0~1) 결정 포트."""

    def size(self, signal: Signal, available_cash: Decimal) -> Decimal:
        """신호와 가용 현금을 받아 투자할 자산 비율(0~1)을 반환한다."""
        ...

    def size_group(
        self,
        signals: Sequence[Signal],
        available_cash: Decimal,
    ) -> Sequence[Decimal]:
        """동일 타임스탬프 신호 그룹을 일괄 처리해 각 신호의 투자 비율을 반환한다.

        WHY: 포트폴리오 전략(EqualWeight, ScoreWeighted 등)은 형제 신호 전체를
             한 번에 받아야 제약(max_position_weight, cash_buffer)을 올바르게 적용할 수 있다.
             반환 리스트의 순서는 입력 signals 의 순서와 동일하다.
        """
        ...
