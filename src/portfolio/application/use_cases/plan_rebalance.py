"""
PlanRebalance 유스케이스.

WHY: min_trade_weight 임계값으로 소규모 거래를 걸러내야 수수료 대비
     실익 없는 리밸런싱 주문을 방지할 수 있다.
     현재 포지션에 없는 종목(신규 진입)과 목표 비중이 0인 종목(완전 청산)도
     delta 계산으로 자연스럽게 처리한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence

from portfolio.application.ports.weight_cap_validator import WeightCapValidator
from portfolio.domain.constraints import PortfolioConstraints
from portfolio.domain.errors import ConstraintViolation
from portfolio.domain.position import CurrentPosition
from portfolio.domain.rebalance_plan import OrderIntent, RebalancePlan
from portfolio.domain.weight import TargetWeight

_ZERO = Decimal("0")
_ONE = Decimal("1")
_DEFAULT_MIN_TRADE_WEIGHT = Decimal("0.01")
_BUY = "BUY"
_SELL = "SELL"


@dataclass(frozen=True)
class PlanRebalance:
    """리밸런싱 계획 수립 유스케이스."""

    min_trade_weight: Decimal = field(
        default_factory=lambda: _DEFAULT_MIN_TRADE_WEIGHT
    )
    constraints: PortfolioConstraints | None = None
    # WHY: M5 S11 — 단일 종목 캡 검증을 외부 어댑터에 위임 가능.
    #      None 이면 기존 인라인 검사 유지 (기본 호환).
    weight_cap_validator: WeightCapValidator | None = None

    def execute(
        self,
        current: Sequence[CurrentPosition],
        targets: Sequence[TargetWeight],
        total_equity: Decimal,
    ) -> RebalancePlan:
        """현재 포지션과 목표 비중을 비교해 리밸런싱 주문 계획을 반환한다."""
        if self.constraints is not None:
            _enforce_constraints(targets, self.constraints, self.weight_cap_validator)
        current_weights = _build_current_weights(current, total_equity)
        target_map = {t.symbol: t.weight for t in targets}
        all_symbols = set(current_weights) | set(target_map)
        intents = tuple(
            _make_intent(sym, current_weights.get(sym, _ZERO), target_map.get(sym, _ZERO))
            for sym in sorted(all_symbols)
            if _is_tradeable(current_weights.get(sym, _ZERO), target_map.get(sym, _ZERO), self.min_trade_weight)
        )
        return RebalancePlan(intents=intents)


def _enforce_constraints(
    targets: Sequence[TargetWeight],
    constraints: PortfolioConstraints,
    validator: WeightCapValidator | None,
) -> None:
    """목표 비중이 제약 조건을 위반하는지 사후 검증한다.

    WHY: ComputeTargetWeights 가 제약을 이미 적용하지만, 외부에서 임의로 구성된
         targets 가 유스케이스에 직접 전달될 수 있으므로 방어선을 한 겹 더 둔다.
         M5 S11: 단일 종목 캡 검사는 validator 가 주입되면 위임,
         아니면 인라인 fallback 으로 동일 의미를 보존한다.
    """
    cap = constraints.max_position_weight
    if validator is not None:
        validator.validate(targets, cap)
    else:
        for t in targets:
            if t.weight > cap:
                raise ConstraintViolation(
                    f"{t.symbol} 목표 비중 {t.weight} 이 max_position_weight {cap} 초과"
                )
    total = sum((t.weight for t in targets), _ZERO)
    max_invested = _ONE - constraints.cash_buffer
    if total > max_invested:
        raise ConstraintViolation(
            f"목표 비중 합계 {total} 이 투자 한도 {max_invested}(=1-cash_buffer) 초과"
        )


def _build_current_weights(
    positions: Sequence[CurrentPosition],
    total_equity: Decimal,
) -> dict[str, Decimal]:
    """현재 보유 포지션을 market_value / total_equity 비중으로 변환한다."""
    if total_equity == _ZERO:
        return {}
    return {p.symbol: p.market_value / total_equity for p in positions}


def _is_tradeable(
    current_w: Decimal,
    target_w: Decimal,
    min_trade: Decimal,
) -> bool:
    """delta 절댓값이 임계값 이상이면 거래 대상으로 판단한다."""
    return abs(target_w - current_w) >= min_trade


def _make_intent(symbol: str, current_w: Decimal, target_w: Decimal) -> OrderIntent:
    """delta 부호에 따라 BUY/SELL OrderIntent 를 생성한다."""
    delta = target_w - current_w
    side = _BUY if delta > _ZERO else _SELL
    return OrderIntent(symbol=symbol, delta_weight=delta, side=side)
