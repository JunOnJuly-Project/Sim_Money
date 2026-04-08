"""EvaluateRisk 유스케이스 — 체인 평가 규칙 테스트 (M5 S2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from risk.application.use_cases import EvaluateRisk
from risk.domain import (
    Allow,
    BlockNew,
    ForceClose,
    RiskContext,
    RiskDecision,
)


_CTX = RiskContext(
    timestamp=datetime(2026, 4, 8, tzinfo=timezone.utc),
    equity=Decimal("10000"),
    peak_equity=Decimal("12000"),
    daily_start_equity=Decimal("11000"),
)


@dataclass(frozen=True)
class _FakeGuard:
    """테스트용 고정 결정 반환 가드."""

    decision: RiskDecision

    def check(self, ctx: RiskContext) -> RiskDecision:  # noqa: ARG002
        return self.decision


class TestEvaluateRisk:
    def test_가드_없으면_Allow(self) -> None:
        result = EvaluateRisk(guards=[]).evaluate(_CTX)
        assert len(result) == 1
        assert isinstance(result[0], Allow)

    def test_모두_Allow_면_단일_Allow(self) -> None:
        uc = EvaluateRisk(guards=[_FakeGuard(Allow()), _FakeGuard(Allow())])
        result = uc.evaluate(_CTX)
        assert len(result) == 1
        assert isinstance(result[0], Allow)

    def test_BlockNew_가_Allow_를_이긴다(self) -> None:
        uc = EvaluateRisk(
            guards=[_FakeGuard(Allow()), _FakeGuard(BlockNew("dd limit"))]
        )
        result = uc.evaluate(_CTX)
        assert len(result) == 1
        assert isinstance(result[0], BlockNew)
        assert result[0].reason == "dd limit"

    def test_ForceClose_가_BlockNew_를_이긴다(self) -> None:
        uc = EvaluateRisk(
            guards=[
                _FakeGuard(BlockNew("daily loss")),
                _FakeGuard(ForceClose("AAA", "stop")),
            ]
        )
        result = uc.evaluate(_CTX)
        assert len(result) == 1
        assert isinstance(result[0], ForceClose)
        assert result[0].symbol == "AAA"

    def test_ForceClose_여러개면_모두_반환(self) -> None:
        uc = EvaluateRisk(
            guards=[
                _FakeGuard(ForceClose("AAA", "stop")),
                _FakeGuard(BlockNew("dd")),
                _FakeGuard(ForceClose("BBB", "stop")),
            ]
        )
        result = uc.evaluate(_CTX)
        assert len(result) == 2
        symbols = {d.symbol for d in result if isinstance(d, ForceClose)}
        assert symbols == {"AAA", "BBB"}
