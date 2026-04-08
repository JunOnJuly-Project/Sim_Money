"""DailyLossLimitGuard (G4) — 일일 손실 한도 (ADR-006).

WHY: 하루 안에 누적 손실이 한도를 넘으면 신규 진입을 막는다. 날짜 경계에서
     daily_start_equity 를 리셋하는 책임은 엔진 조립 계층(S8)에 있다.
     가드 자체는 순수 함수 — (equity - daily_start) / daily_start 만 비교.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from risk.domain import Allow, BlockNew, RiskContext, RiskDecision, RiskDomainError

_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True)
class DailyLossLimitGuard:
    """일일 최대 허용 손실률.

    Attributes:
        max_daily_loss: (0, 1] 범위. 0.03 = 당일 -3% 도달 시 신규 진입 차단.
    """

    max_daily_loss: Decimal

    def __post_init__(self) -> None:
        if self.max_daily_loss <= _ZERO or self.max_daily_loss > _ONE:
            raise RiskDomainError(
                f"max_daily_loss({self.max_daily_loss}) 는 (0, 1] 범위여야 한다"
            )

    def check(self, ctx: RiskContext) -> RiskDecision:
        if ctx.candidate_symbol is None:
            return Allow()
        threshold = -self.max_daily_loss
        if ctx.daily_pnl_pct <= threshold:
            return BlockNew(
                reason=(
                    f"당일 손익률 {ctx.daily_pnl_pct} 이 한도 -{self.max_daily_loss} 이하"
                )
            )
        return Allow()
