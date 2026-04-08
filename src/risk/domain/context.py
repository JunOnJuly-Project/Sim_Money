"""RiskContext — 가드 체인 평가에 필요한 스냅샷.

WHY: 가드는 순수 함수여야 한다. 엔진 내부 상태(Portfolio/Position)와 결합하지 않도록
     독자 값 객체 PositionSnapshot / RiskContext 를 정의하고, backtest 어댑터가 매 bar
     매핑해 주입한다 (ADR-006).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Tuple

from .errors import RiskDomainError

_ZERO = Decimal("0")


@dataclass(frozen=True)
class PositionSnapshot:
    """단일 포지션 스냅샷 — 가드가 참조하는 최소 정보."""

    symbol: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal

    def __post_init__(self) -> None:
        if not self.symbol:
            raise RiskDomainError("symbol 은 비어 있을 수 없다")
        if self.quantity <= _ZERO:
            raise RiskDomainError(f"quantity({self.quantity}) 는 양수여야 한다")
        if self.entry_price <= _ZERO:
            raise RiskDomainError(f"entry_price({self.entry_price}) 는 양수여야 한다")
        if self.current_price <= _ZERO:
            raise RiskDomainError(
                f"current_price({self.current_price}) 는 양수여야 한다"
            )

    @property
    def notional(self) -> Decimal:
        """현재가 기준 명목 금액."""
        return self.quantity * self.current_price

    @property
    def unrealized_pnl_pct(self) -> Decimal:
        """미실현 손익률 — (현재가 - 진입가) / 진입가."""
        return (self.current_price - self.entry_price) / self.entry_price


@dataclass(frozen=True)
class RiskContext:
    """가드 평가 스냅샷.

    Attributes:
        timestamp: 현재 bar 시각 (일일 경계 판정용)
        equity: 계좌 총자산 (현금 + 포지션 시가)
        peak_equity: 세션 내 equity 최고치 (드로다운 계산)
        daily_start_equity: 당일 시작 equity (일일 손실 계산)
        positions: 현재 열린 포지션 스냅샷 튜플
        candidate_symbol: 진입 후보 심볼 (없으면 None)
        candidate_notional: 진입 후보 명목 금액 (없으면 None)
        available_cash: 가용 현금 (선택) — 향후 마진/현금 가드 확장 지점.
            기본 None 이면 가드는 equity 만 참조한다.
    """

    timestamp: datetime
    equity: Decimal
    peak_equity: Decimal
    daily_start_equity: Decimal
    positions: Tuple[PositionSnapshot, ...] = field(default_factory=tuple)
    candidate_symbol: str | None = None
    candidate_notional: Decimal | None = None
    available_cash: Decimal | None = None

    def __post_init__(self) -> None:
        if self.equity <= _ZERO:
            raise RiskDomainError(f"equity({self.equity}) 는 양수여야 한다")
        if self.peak_equity < self.equity:
            raise RiskDomainError(
                f"peak_equity({self.peak_equity}) 는 equity({self.equity}) 이상이어야 한다"
            )
        if self.daily_start_equity <= _ZERO:
            raise RiskDomainError(
                f"daily_start_equity({self.daily_start_equity}) 는 양수여야 한다"
            )
        if (self.candidate_symbol is None) != (self.candidate_notional is None):
            raise RiskDomainError(
                "candidate_symbol 과 candidate_notional 은 함께 제공되거나 함께 생략되어야 한다"
            )
        if self.candidate_notional is not None and self.candidate_notional <= _ZERO:
            raise RiskDomainError(
                f"candidate_notional({self.candidate_notional}) 는 양수여야 한다"
            )

    @property
    def drawdown_pct(self) -> Decimal:
        """현재 드로다운 비율 — (peak - equity) / peak. 음수 불가."""
        return (self.peak_equity - self.equity) / self.peak_equity

    @property
    def daily_pnl_pct(self) -> Decimal:
        """당일 손익률 — (equity - daily_start) / daily_start."""
        return (self.equity - self.daily_start_equity) / self.daily_start_equity
