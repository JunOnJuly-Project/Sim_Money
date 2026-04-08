"""ExitAdvisor 포트 — 강제 청산 권고 (M5 S14, ADR-007 후보).

WHY: EntryFilter 는 진입 후보만 차단한다. 보유 포지션의 손실률이 한도를
     초과해 즉시 청산이 필요한 경우(StopLossGuard.ForceClose 등)에는
     엔진이 매 bar 마다 advisor 를 호출해 강제 EXIT 대상 심볼을 받아야 한다.

     advisor 는 application 레이어에서 어떤 risk 타입도 import 하지 않는다.
     PositionView 는 stdlib Decimal 만 사용하는 순수 dataclass 이며,
     실제 risk 가드 변환은 backtest.adapters.outbound.risk_exit_advisor 에서 수행한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Mapping, Protocol, Sequence


@dataclass(frozen=True)
class PositionView:
    """advisor 평가용 포지션 스냅샷 (도메인 Position 의 읽기 전용 뷰)."""

    symbol: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal


class ExitAdvisor(Protocol):
    """매 bar 호출되어 강제 청산 대상 심볼 목록을 반환한다."""

    def advise(
        self,
        timestamp: datetime,
        positions: Mapping[str, PositionView],
        available_cash: Decimal,
        equity: Decimal,
    ) -> Sequence[str]:
        """청산할 심볼 목록을 반환한다. 비어 있으면 강제 청산 없음."""
        ...
