"""RiskEntryFilter — risk 가드를 EntryFilter 로 브릿지 (M5 S9).

WHY: backtest.application 이 risk L3 도메인을 직접 import 하지 않도록
     어댑터 레이어에서 EntryFilter 포트를 구현한다 (ADR-005).
     PositionLimit/Drawdown/DailyLoss 세 BlockNew-type 가드를 체인으로 구성해
     진입 후보를 하나씩 평가한다. 세션 내 peak_equity 와 당일 시작 equity 는
     filter 호출마다 갱신한다.
"""

from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Sequence

from backtest.domain.signal import Signal
from risk.application.use_cases import EvaluateRisk
from risk.application.ports import RiskGuard
from risk.domain import Allow, RiskContext


class RiskEntryFilter:
    """EntryFilter 구현 — 가드 체인으로 후보를 축소한다."""

    def __init__(self, guards: Sequence[RiskGuard]) -> None:
        self._evaluator = EvaluateRisk(guards=guards)
        self._peak_equity: Decimal | None = None
        self._daily_start_equity: Decimal | None = None
        self._current_day: date | None = None

    def filter(
        self,
        timestamp: datetime,
        candidates: Sequence[Signal],
        available_cash: Decimal,
        equity: Decimal,
    ) -> Sequence[Signal]:
        # 세션 peak 갱신
        if self._peak_equity is None or equity > self._peak_equity:
            self._peak_equity = equity
        # 일일 경계 리셋
        day = timestamp.date()
        if self._current_day != day:
            self._current_day = day
            self._daily_start_equity = equity

        allowed: list[Signal] = []
        for candidate in candidates:
            notional = candidate.strength * available_cash / max(Decimal(len(candidates)), Decimal("1"))
            if notional <= Decimal("0"):
                continue
            ctx = RiskContext(
                timestamp=timestamp,
                equity=equity,
                peak_equity=self._peak_equity,
                daily_start_equity=self._daily_start_equity or equity,
                candidate_symbol=candidate.ticker,
                candidate_notional=notional,
            )
            decisions = self._evaluator.evaluate(ctx)
            if all(isinstance(d, Allow) for d in decisions):
                allowed.append(candidate)
        return allowed
