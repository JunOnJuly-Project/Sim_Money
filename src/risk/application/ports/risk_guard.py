"""RiskGuard 포트 (ADR-006).

WHY: 4 가드(PositionLimit/StopLoss/Drawdown/DailyLoss)가 동일 Protocol 로 체인 평가
     가능하도록 한다. 가드는 RiskContext 만 받는 순수 함수이며 부작용이 없다.
"""

from __future__ import annotations

from typing import Protocol

from risk.domain import RiskContext, RiskDecision


class RiskGuard(Protocol):
    """가드 단일 책임: 컨텍스트를 보고 결정을 반환한다."""

    def check(self, ctx: RiskContext) -> RiskDecision:
        ...
