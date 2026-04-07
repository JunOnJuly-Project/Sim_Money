"""
WeightingStrategy 포트 인터페이스 + SignalInput DTO.

WHY: 가중치 계산 전략을 Strategy 패턴으로 교체 가능하게 하려면
     포트 인터페이스가 필요하다. Protocol 로 정의해 다양한 전략
     구현체(EqualWeight, RiskParity 등)를 런타임에 교체할 수 있다.

     SignalInput 은 외부 trading_signal 패키지 의존을 끊기 위한
     portfolio 전용 DTO 다. ADR-004 결정 2 참조.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, Sequence

from portfolio.domain.constraints import PortfolioConstraints
from portfolio.domain.weight import TargetWeight


@dataclass(frozen=True)
class SignalInput:
    """가중치 계산 입력 DTO.

    WHY: trading_signal 패키지에 직접 의존하지 않고 portfolio 가
         자체 DTO 로 경계를 명시해 L3 레이어 오염을 방지한다.
    """

    symbol: str
    score: Decimal


class WeightingStrategy(Protocol):
    """가중치 계산 전략 포트."""

    def compute(
        self,
        signals: Sequence[SignalInput],
        constraints: PortfolioConstraints,
    ) -> tuple[TargetWeight, ...]:
        """시그널과 제약 조건을 받아 목표 비중 튜플을 반환한다."""
        ...
