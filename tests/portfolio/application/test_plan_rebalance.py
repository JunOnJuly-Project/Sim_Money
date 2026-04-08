"""
PlanRebalance 유스케이스 단위 테스트.

WHY: 신규 진입/청산/부분/임계값 무시 등 경계 케이스를 격리 검증해
     리밸런싱 로직의 회귀를 방지한다.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from portfolio.application.use_cases.plan_rebalance import PlanRebalance
from portfolio.domain.position import CurrentPosition
from portfolio.domain.weight import TargetWeight

_EQUITY = Decimal("1000000")
_MIN_TRADE = Decimal("0.01")


def _pos(symbol: str, value: str) -> CurrentPosition:
    """테스트용 CurrentPosition 헬퍼."""
    return CurrentPosition(symbol=symbol, quantity=Decimal("1"), market_value=Decimal(value))


def _tw(symbol: str, weight: str) -> TargetWeight:
    """테스트용 TargetWeight 헬퍼."""
    return TargetWeight(symbol=symbol, weight=Decimal(weight))


# --- 테스트 ---

def test_빈_입력_빈_계획():
    uc = PlanRebalance()
    plan = uc.execute([], [], _EQUITY)
    assert plan.intents == ()


def test_신규_진입_buy_생성():
    """현재 포지션 없고 목표 비중 있으면 BUY 주문이어야 한다."""
    uc = PlanRebalance()
    plan = uc.execute([], [_tw("A", "0.5")], _EQUITY)
    assert len(plan.intents) == 1
    intent = plan.intents[0]
    assert intent.symbol == "A"
    assert intent.side == "BUY"
    assert intent.delta_weight == Decimal("0.5")


def test_완전_청산_sell_생성():
    """목표 비중 0이고 현재 포지션 있으면 SELL 주문이어야 한다."""
    uc = PlanRebalance()
    plan = uc.execute([_pos("A", "500000")], [_tw("A", "0")], _EQUITY)
    assert len(plan.intents) == 1
    assert plan.intents[0].side == "SELL"
    assert plan.intents[0].delta_weight == Decimal("-0.5")


def test_부분_리밸런싱():
    """현재 40%, 목표 60% 이면 BUY delta=0.20 이어야 한다."""
    uc = PlanRebalance()
    plan = uc.execute([_pos("A", "400000")], [_tw("A", "0.6")], _EQUITY)
    assert len(plan.intents) == 1
    assert plan.intents[0].side == "BUY"
    assert abs(plan.intents[0].delta_weight - Decimal("0.2")) < Decimal("1e-9")


def test_임계값_미만_무시():
    """delta 가 min_trade_weight 미만이면 주문을 생성하지 않는다."""
    uc = PlanRebalance(min_trade_weight=Decimal("0.01"))
    plan = uc.execute([_pos("A", "500000")], [_tw("A", "0.505")], _EQUITY)
    assert plan.intents == ()


def test_임계값_정확히_같으면_포함():
    """delta 가 min_trade_weight 와 정확히 같으면 주문을 생성해야 한다."""
    uc = PlanRebalance(min_trade_weight=Decimal("0.01"))
    plan = uc.execute([_pos("A", "500000")], [_tw("A", "0.51")], _EQUITY)
    assert len(plan.intents) == 1


def test_복수_종목_혼합():
    """매수/매도/무시 케이스가 혼재할 때 올바르게 분류해야 한다."""
    uc = PlanRebalance(min_trade_weight=Decimal("0.01"))
    current = [_pos("A", "300000"), _pos("B", "300000"), _pos("C", "300000")]
    targets = [_tw("A", "0.5"), _tw("B", "0.305"), _tw("C", "0.3")]
    plan = uc.execute(current, targets, _EQUITY)
    sides = {i.symbol: i.side for i in plan.intents}
    assert sides["A"] == "BUY"
    assert "B" not in sides   # delta = 0.005 < 0.01, 무시
    assert "C" not in sides   # delta = 0, 무시


def test_delta_합계_보존():
    """모든 종목 delta 의 합은 (목표 비중 합 - 현재 비중 합) 과 같아야 한다."""
    uc = PlanRebalance(min_trade_weight=Decimal("0"))
    current = [_pos("A", "400000"), _pos("B", "400000")]
    targets = [_tw("A", "0.3"), _tw("B", "0.5"), _tw("C", "0.2")]
    plan = uc.execute(current, targets, _EQUITY)
    delta_sum = sum(i.delta_weight for i in plan.intents)
    # 현재 합=0.8, 목표 합=1.0 → delta 합=0.2
    assert abs(delta_sum - Decimal("0.2")) < Decimal("1e-9")


def test_total_equity_가_0_이면_현재_비중이_모두_0_으로_처리된다():
    """WHY: 방어적 분기 (보통 상위에서 validate 되지만 단위 커버리지를 보장한다)."""
    uc = PlanRebalance(min_trade_weight=Decimal("0"))
    current = [_pos("A", "500000")]
    targets = [_tw("A", "0.5")]
    plan = uc.execute(current, targets, Decimal("0"))
    # 현재 비중=0 (total_equity=0), 목표=0.5 → BUY delta=0.5
    assert len(plan.intents) == 1
    assert plan.intents[0].side == "BUY"
    assert plan.intents[0].delta_weight == Decimal("0.5")


# ── 제약 사후 검증 ────────────────────────────────────────────────────────

def test_constraints_주입시_max_position_weight_초과는_ConstraintViolation():
    """WHY: 외부에서 임의로 구성된 targets 가 제약을 위반해도 유스케이스에서 차단한다."""
    from portfolio.domain.constraints import PortfolioConstraints
    from portfolio.domain.errors import ConstraintViolation

    constraints = PortfolioConstraints(
        max_position_weight=Decimal("0.3"),
        cash_buffer=Decimal("0"),
    )
    uc = PlanRebalance(min_trade_weight=Decimal("0"), constraints=constraints)
    targets = [_tw("A", "0.5")]  # 0.3 초과
    with pytest.raises(ConstraintViolation, match="max_position_weight"):
        uc.execute([], targets, _EQUITY)


def test_constraints_주입시_cash_buffer_위반하면_ConstraintViolation():
    """WHY: 목표 비중 합이 1 - cash_buffer 를 초과하면 투자 한도 위반."""
    from portfolio.domain.constraints import PortfolioConstraints
    from portfolio.domain.errors import ConstraintViolation

    constraints = PortfolioConstraints(
        max_position_weight=Decimal("1"),
        cash_buffer=Decimal("0.2"),
    )
    uc = PlanRebalance(min_trade_weight=Decimal("0"), constraints=constraints)
    targets = [_tw("A", "0.5"), _tw("B", "0.4")]  # 합=0.9 > 0.8
    with pytest.raises(ConstraintViolation, match="cash_buffer"):
        uc.execute([], targets, _EQUITY)


def test_constraints_미주입이면_제약_검증없이_통과():
    """WHY: 기본값 None 이면 하위 호환 — 기존 호출부는 제약 검증 없이 동작한다."""
    uc = PlanRebalance(min_trade_weight=Decimal("0"))
    targets = [_tw("A", "0.99")]
    plan = uc.execute([], targets, _EQUITY)
    assert len(plan.intents) == 1
