"""RiskSessionState — 가드 어댑터 간 세션 추적 단일 진실원 (M5 follow-up).

WHY: RiskEntryFilter 와 RiskExitAdvisor 가 각자 peak_equity / daily_start_equity
     를 독립 추적하면 호출 빈도가 다를 때(EntryFilter 는 LONG 후보 시점만,
     ExitAdvisor 는 매 bar) 세션 peak 가 어긋나 가드 의미가 모순된다.
     본 객체를 두 어댑터가 공유하면 항상 동일한 peak/daily 기준으로 평가한다.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal


class RiskSessionState:
    """가드 평가에 필요한 세션 누적 상태."""

    def __init__(self) -> None:
        self._peak_equity: Decimal | None = None
        self._daily_start_equity: Decimal | None = None
        self._current_day: date | None = None

    def observe(self, timestamp: datetime, equity: Decimal) -> None:
        """현재 equity 를 관측하여 peak·일일 시작값을 갱신한다."""
        if self._peak_equity is None or equity > self._peak_equity:
            self._peak_equity = equity
        day = timestamp.date()
        if self._current_day != day:
            self._current_day = day
            self._daily_start_equity = equity

    @property
    def peak_equity(self) -> Decimal | None:
        return self._peak_equity

    @property
    def daily_start_equity(self) -> Decimal | None:
        return self._daily_start_equity
