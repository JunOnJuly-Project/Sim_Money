"""DrawdownCircuitBreaker (G3) — 누적 드로다운 한도 차단 (ADR-006).

WHY: 피크 대비 누적 손실이 한도를 넘으면 신규 진입을 막아 추가 손실을 제한한다.
     후보가 없을 때는 Allow 를 반환한다 — 기존 포지션은 건드리지 않는다
     (StopLossGuard 가 개별 청산을 담당).
     세션 내 해제 없음 — 한 번 트리거되면 해당 backtest/세션 동안 차단 유지.
     (peak_equity 는 엔진이 갱신하지 않으므로 DD 가 낮아져도 다시 Allow 로 돌아감;
      '세션 내 유지'는 엔진 조립 계층의 책임으로 S8 에서 구현.)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from risk.domain import Allow, BlockNew, RiskContext, RiskDecision, RiskDomainError

_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True)
class DrawdownCircuitBreaker:
    """최대 허용 드로다운 비율.

    Attributes:
        max_drawdown: (0, 1] 범위의 허용 DD. 0.2 = 20% 초과 시 차단.
    """

    max_drawdown: Decimal

    def __post_init__(self) -> None:
        if self.max_drawdown <= _ZERO or self.max_drawdown > _ONE:
            raise RiskDomainError(
                f"max_drawdown({self.max_drawdown}) 는 (0, 1] 범위여야 한다"
            )

    def check(self, ctx: RiskContext) -> RiskDecision:
        if ctx.candidate_symbol is None:
            return Allow()
        if ctx.drawdown_pct > self.max_drawdown:
            return BlockNew(
                reason=(
                    f"누적 드로다운 {ctx.drawdown_pct} 이 한도 {self.max_drawdown} 초과"
                )
            )
        return Allow()
