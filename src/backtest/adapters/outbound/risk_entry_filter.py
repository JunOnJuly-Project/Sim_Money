"""RiskEntryFilter — risk 가드를 EntryFilter 로 브릿지 (M5 S9).

WHY: backtest.application 이 risk L3 도메인을 직접 import 하지 않도록
     어댑터 레이어에서 EntryFilter 포트를 구현한다 (ADR-005).
     PositionLimit/Drawdown/DailyLoss 세 BlockNew-type 가드를 체인으로 구성해
     진입 후보를 하나씩 평가한다. 세션 내 peak_equity 와 당일 시작 equity 는
     filter 호출마다 갱신한다.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Sequence

from backtest.adapters.outbound.risk_session_state import RiskSessionState
from backtest.domain.signal import Signal
from risk.application.use_cases import EvaluateRisk
from risk.application.ports import RiskGuard
from risk.domain import Allow, RiskContext


class RiskEntryFilter:
    """EntryFilter 구현 — 가드 체인으로 후보를 축소한다."""

    def __init__(
        self,
        guards: Sequence[RiskGuard],
        session_state: RiskSessionState | None = None,
    ) -> None:
        self._evaluator = EvaluateRisk(guards=guards)
        # WHY: session_state 를 외부에서 주입하면 RiskExitAdvisor 와 동일 인스턴스를
        #      공유해 peak/daily 추적이 단일 진실원이 된다 (review followup #2).
        self._session = session_state or RiskSessionState()

    def filter(
        self,
        timestamp: datetime,
        candidates: Sequence[Signal],
        available_cash: Decimal,
        equity: Decimal,
    ) -> Sequence[Signal]:
        self._session.observe(timestamp, equity)

        allowed: list[Signal] = []
        for candidate in candidates:
            notional = candidate.strength * available_cash / max(Decimal(len(candidates)), Decimal("1"))
            if notional <= Decimal("0"):
                continue
            ctx = RiskContext(
                timestamp=timestamp,
                equity=equity,
                peak_equity=self._session.peak_equity or equity,
                daily_start_equity=self._session.daily_start_equity or equity,
                candidate_symbol=candidate.ticker,
                candidate_notional=notional,
            )
            decisions = self._evaluator.evaluate(ctx)
            if all(isinstance(d, Allow) for d in decisions):
                allowed.append(candidate)
        return allowed
