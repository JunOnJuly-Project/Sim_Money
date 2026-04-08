"""RiskDecision — 가드 체인 결정 값 객체.

WHY: 가드 결과를 합집합 타입(Allow/BlockNew/ForceClose)으로 표현해
     체인 평가 시 '가장 보수적 결정 우선' 규칙을 간단히 비교 가능하게 한다 (ADR-006).
     우선순위: ForceClose > BlockNew > Allow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .errors import RiskDomainError


@dataclass(frozen=True)
class Allow:
    """진입/유지 허용."""

    reason: str = ""

    @property
    def severity(self) -> int:
        return 0


@dataclass(frozen=True)
class BlockNew:
    """신규 진입 차단 — 기존 포지션은 유지."""

    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise RiskDomainError("BlockNew 는 reason 이 필요하다")

    @property
    def severity(self) -> int:
        return 1


@dataclass(frozen=True)
class ForceClose:
    """특정 심볼 강제 청산."""

    symbol: str
    reason: str

    def __post_init__(self) -> None:
        if not self.symbol:
            raise RiskDomainError("ForceClose 는 symbol 이 필요하다")
        if not self.reason:
            raise RiskDomainError("ForceClose 는 reason 이 필요하다")

    @property
    def severity(self) -> int:
        return 2


RiskDecision = Union[Allow, BlockNew, ForceClose]
