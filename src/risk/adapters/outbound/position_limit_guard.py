"""PositionLimitGuard (G1) — 단일 심볼 비중 한도 (ADR-006).

WHY: 한 종목에 자본이 과도하게 몰리는 것을 방지한다. 진입 후보가 있으면
     (기존 같은 심볼 포지션 + 후보 명목) / equity 가 max_weight 이하인지 검사한다.
     후보가 없으면 기존 포지션만 검사 — 시세 변동으로 한도가 돌파되면 BlockNew.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from risk.domain import Allow, BlockNew, RiskContext, RiskDecision, RiskDomainError

_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True)
class PositionLimitGuard:
    """최대 포지션 비중 한도.

    Attributes:
        max_weight: (0, 1] 범위의 단일 심볼 최대 비중.
    """

    max_weight: Decimal

    def __post_init__(self) -> None:
        if self.max_weight <= _ZERO or self.max_weight > _ONE:
            raise RiskDomainError(
                f"max_weight({self.max_weight}) 는 (0, 1] 범위여야 한다"
            )

    def check(self, ctx: RiskContext) -> RiskDecision:
        cap = self.max_weight * ctx.equity
        # 기존 포지션별 명목 합 (심볼별 누적)
        existing: dict[str, Decimal] = {}
        for pos in ctx.positions:
            existing[pos.symbol] = existing.get(pos.symbol, _ZERO) + pos.notional

        # 기존 포지션이 이미 한도 초과면 차단
        for symbol, notional in existing.items():
            if notional > cap:
                return BlockNew(
                    reason=f"{symbol} 비중 {notional / ctx.equity} 이 한도 {self.max_weight} 초과"
                )

        if ctx.candidate_symbol is None:
            return Allow()

        assert ctx.candidate_notional is not None  # RiskContext 불변식이 보장
        projected = existing.get(ctx.candidate_symbol, _ZERO) + ctx.candidate_notional
        if projected > cap:
            return BlockNew(
                reason=(
                    f"{ctx.candidate_symbol} 진입 후 비중 "
                    f"{projected / ctx.equity} 이 한도 {self.max_weight} 초과"
                )
            )
        return Allow()
