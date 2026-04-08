"""RiskWeightCapValidator — risk.PositionLimitGuard 재사용 어댑터 (M5 S11).

WHY: PlanRebalance 가 사용하던 인라인 cap 검사를 risk 도메인의
     PositionLimitGuard 로 위임해 단일 종목 한도 의미를 한 곳에서 관리한다.
     equity=1 / candidate_notional=weight 매핑으로 동일한 부등식
     (weight > max_position_weight) 을 PositionLimitGuard 가 평가하도록 한다.
     L3↔L3 수평 의존은 어댑터 레이어에서만 허용 (ADR-005).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

from portfolio.domain.errors import ConstraintViolation
from portfolio.domain.weight import TargetWeight
from risk.adapters.outbound.position_limit_guard import PositionLimitGuard
from risk.domain import Allow, BlockNew, RiskContext

# WHY: RiskContext.timestamp 는 일일 경계 판정용 — 캡 검증 경로에서는 의미 없음.
#      도메인 결정성을 위해 고정 epoch 값을 사용한다.
_FIXED_TS = datetime(2000, 1, 1, tzinfo=timezone.utc)
_ONE = Decimal("1")
_ZERO = Decimal("0")


class RiskWeightCapValidator:
    """PositionLimitGuard 로 단일 종목 캡을 위임 검증한다."""

    def validate(
        self,
        targets: Sequence[TargetWeight],
        max_position_weight: Decimal,
    ) -> None:
        """단일 종목 캡을 검사한다.

        정책:
            - weight == 0 → 비활성 포지션(검증 대상 아님) 으로 간주해 건너뛴다.
              PositionLimitGuard 는 양수 notional 만 받는 제약도 있다.
            - weight < 0 → TargetWeight 값 객체 불변식 (0 ≤ weight ≤ 1) 이 이미
              생성 시점에 차단하므로 이 경로에 도달하면 안 된다. 방어적으로
              `ConstraintViolation` 으로 즉시 실패시킨다.
            - 0 < weight ≤ max_weight → Allow
            - weight > max_weight → ConstraintViolation
        """
        guard = PositionLimitGuard(max_weight=max_position_weight)
        for t in targets:
            if t.weight < _ZERO:
                raise ConstraintViolation(
                    f"{t.symbol} 목표 비중 {t.weight} 이 음수 (불변식 위반)"
                )
            if t.weight == _ZERO:
                continue
            ctx = RiskContext(
                timestamp=_FIXED_TS,
                equity=_ONE,
                peak_equity=_ONE,
                daily_start_equity=_ONE,
                candidate_symbol=t.symbol,
                candidate_notional=t.weight,
            )
            decision = guard.check(ctx)
            if isinstance(decision, BlockNew):
                raise ConstraintViolation(
                    f"{t.symbol} 목표 비중 {t.weight} 이 "
                    f"max_position_weight {max_position_weight} 초과"
                )
            assert isinstance(decision, Allow)  # 가드 의미상 다른 결정 불가
