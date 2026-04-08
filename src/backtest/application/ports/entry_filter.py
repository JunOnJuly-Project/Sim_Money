"""EntryFilter 포트 — 진입 후보 필터링.

WHY: 리스크 가드 같은 외부 정책을 RunBacktest 에 주입하기 위한 얇은 훅.
     backtest.application 이 risk L3 를 직접 import 하는 것을 피하기 위해
     Protocol 을 여기에 두고, 구현(예: RiskEntryFilter)은 backtest.adapters 에 둔다.
     ADR-005 L3↔L3 수평 의존은 어댑터 레이어에서만 허용.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol, Sequence

from backtest.domain.signal import Signal


class EntryFilter(Protocol):
    """진입 후보 필터.

    매 timestamp 그룹 진입 직전 호출되어, 허용된 후보만 추려 반환한다.
    순수 함수일 필요는 없음 — 어댑터는 세션 내부 상태(예: DD 트리거 래칭) 유지 가능.
    """

    def filter(
        self,
        timestamp: datetime,
        candidates: Sequence[Signal],
        available_cash: Decimal,
        equity: Decimal,
    ) -> Sequence[Signal]:
        ...
