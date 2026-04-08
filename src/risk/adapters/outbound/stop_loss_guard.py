"""StopLossGuard (G2) — 포지션별 손절 (ADR-006).

WHY: 미실현 손실률이 한도를 초과한 포지션을 강제 청산해 손실을 제한한다.
     여러 포지션이 동시에 한도를 넘으면 EvaluateRisk 가 모두 모아 반환한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from risk.domain import (
    Allow,
    ForceClose,
    RiskContext,
    RiskDecision,
    RiskDomainError,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True)
class StopLossGuard:
    """포지션 손절 비율.

    Attributes:
        max_loss_pct: (0, 1] 범위의 최대 허용 손실률. 0.05 = -5% 도달 시 청산.
    """

    max_loss_pct: Decimal

    def __post_init__(self) -> None:
        if self.max_loss_pct <= _ZERO or self.max_loss_pct > _ONE:
            raise RiskDomainError(
                f"max_loss_pct({self.max_loss_pct}) 는 (0, 1] 범위여야 한다"
            )

    def check(self, ctx: RiskContext) -> RiskDecision:
        # WHY: 손절 트리거는 pnl <= -max_loss_pct. 첫 포지션만 반환해도 무방하지만
        #      엔진이 한 틱에 다중 청산을 처리할 수 있도록 첫 번째만 반환하되
        #      EvaluateRisk 가 여러 StopLossGuard 를 체인에 두지 않는다는 가정을 지킴.
        #      S8 엔진 통합에서는 포지션마다 단일 가드를 호출한다.
        threshold = -self.max_loss_pct
        for pos in ctx.positions:
            if pos.unrealized_pnl_pct <= threshold:
                return ForceClose(
                    symbol=pos.symbol,
                    reason=f"손실률 {pos.unrealized_pnl_pct} <= -{self.max_loss_pct}",
                )
        return Allow()
