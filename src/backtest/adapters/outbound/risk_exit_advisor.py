"""RiskExitAdvisor — risk 가드 ForceClose 를 EXIT 권고로 변환 (M5 S14).

WHY: backtest.application 이 risk 도메인을 직접 import 하지 않도록 어댑터에서
     ExitAdvisor 포트를 구현한다 (ADR-005). StopLossGuard 등 ForceClose 를
     반환하는 가드를 체인으로 평가해 청산 대상 심볼 목록을 산출한다.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Mapping, Sequence

from backtest.adapters.outbound.risk_session_state import RiskSessionState
from backtest.application.ports.exit_advisor import PositionView
from risk.application.ports import RiskGuard
from risk.application.use_cases import EvaluateRisk
from risk.domain import ForceClose, PositionSnapshot, RiskContext


class RiskExitAdvisor:
    """ExitAdvisor 구현 — 가드 체인의 ForceClose 결정을 청산 심볼로 매핑한다."""

    def __init__(
        self,
        guards: Sequence[RiskGuard],
        session_state: RiskSessionState | None = None,
    ) -> None:
        self._evaluator = EvaluateRisk(guards=guards)
        # WHY: 외부에서 주입하면 RiskEntryFilter 와 동일 세션 상태를 공유한다.
        self._session = session_state or RiskSessionState()

    def advise(
        self,
        timestamp: datetime,
        positions: Mapping[str, PositionView],
        available_cash: Decimal,  # noqa: ARG002 - 가드 체인은 equity 만 사용
        equity: Decimal,
    ) -> Sequence[str]:
        if not positions:
            return []

        self._session.observe(timestamp, equity)

        snapshots = tuple(
            PositionSnapshot(
                symbol=pv.symbol,
                quantity=pv.quantity,
                entry_price=pv.entry_price,
                current_price=pv.current_price,
            )
            for pv in positions.values()
        )
        ctx = RiskContext(
            timestamp=timestamp,
            equity=equity,
            peak_equity=self._session.peak_equity or equity,
            daily_start_equity=self._session.daily_start_equity or equity,
            positions=snapshots,
        )
        decisions = self._evaluator.evaluate(ctx)
        return [d.symbol for d in decisions if isinstance(d, ForceClose)]
