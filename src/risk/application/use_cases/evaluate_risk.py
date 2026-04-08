"""EvaluateRisk — 가드 체인 평가 유스케이스.

WHY: 여러 RiskGuard 의 결정을 하나로 축약한다. 규칙은 '가장 보수적 결정 우선'
     (severity 가 큰 결정이 이김). ForceClose 가 여러 심볼에 대해 발생하면
     모두 모아 반환하기 위해 결과를 튜플로 제공한다 (ADR-006).

체인 평가 규칙:
- 최대 severity 를 찾는다
- severity == 0 (Allow only) → 단일 Allow 반환
- severity == 1 (BlockNew 존재, ForceClose 없음) → 첫 BlockNew 반환
- severity == 2 (ForceClose 존재) → 모든 ForceClose 를 튜플로 반환
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from risk.application.ports import RiskGuard
from risk.domain import Allow, BlockNew, ForceClose, RiskContext, RiskDecision


@dataclass(frozen=True)
class EvaluateRisk:
    """가드 체인을 주입받아 평가하는 얇은 유스케이스."""

    guards: Sequence[RiskGuard]

    def evaluate(self, ctx: RiskContext) -> Tuple[RiskDecision, ...]:
        decisions = [guard.check(ctx) for guard in self.guards]
        if not decisions:
            return (Allow(reason="no guards"),)

        max_severity = max(d.severity for d in decisions)
        if max_severity == 0:
            return (Allow(),)
        if max_severity == 1:
            # WHY: 첫 BlockNew 의 reason 을 대표로 노출. 여러 BlockNew 가 있어도 효과는 동일.
            for d in decisions:
                if isinstance(d, BlockNew):
                    return (d,)
        # max_severity == 2 — 모든 ForceClose 를 순서대로 반환
        force_closes = tuple(d for d in decisions if isinstance(d, ForceClose))
        return force_closes
