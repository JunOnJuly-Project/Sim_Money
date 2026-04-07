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

from portfolio.domain.position import CurrentPosition
from portfolio.domain.rebalance_plan import OrderIntent, RebalancePlan
from portfolio.domain.weight import TargetWeight

_ZERO = Decimal("0")
_DEFAULT_MIN_TRADE_WEIGHT = Decimal("0.01")
_BUY = "BUY"
_SELL = "SELL"


@dataclass(frozen=True)
class PlanRebalance:
    """리밸런싱 계획 수립 유스케이스."""

    min_trade_weight: Decimal = field(
        default_factory=lambda: _DEFAULT_MIN_TRADE_WEIGHT
    )

    def execute(
        self,
        current: Sequence[CurrentPosition],
        targets: Sequence[TargetWeight],
        total_equity: Decimal,
    ) -> RebalancePlan:
        """현재 포지션과 목표 비중을 비교해 리밸런싱 주문 계획을 반환한다."""
        current_weights = _build_current_weights(current, total_equity)
        target_map = {t.symbol: t.weight for t in targets}
        all_symbols = set(current_weights) | set(target_map)
        intents = tuple(
            _make_intent(sym, current_weights.get(sym, _ZERO), target_map.get(sym, _ZERO))
            for sym in sorted(all_symbols)
            if _is_tradeable(current_weights.get(sym, _ZERO), target_map.get(sym, _ZERO), self.min_trade_weight)
        )
        return RebalancePlan(intents=intents)


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
