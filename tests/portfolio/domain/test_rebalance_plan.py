"""
OrderIntent + RebalancePlan 도메인 값 객체 단위 테스트.
"""
import pytest
from decimal import Decimal

from portfolio.domain.rebalance_plan import OrderIntent, RebalancePlan

_SYMBOL = "AAPL"
_DELTA_BUY = Decimal("0.1")
_DELTA_SELL = Decimal("-0.1")
_ZERO = Decimal("0")


# ──────────────────────────────── OrderIntent ─────────────────────────────────

def test_BUY_양수_delta_생성_성공():
    """BUY side 와 양수 delta_weight 로 생성 가능해야 한다."""
    intent = OrderIntent(symbol=_SYMBOL, delta_weight=_DELTA_BUY, side="BUY")
    assert intent.side == "BUY"
    assert intent.delta_weight == _DELTA_BUY


def test_SELL_음수_delta_생성_성공():
    """SELL side 와 음수 delta_weight 로 생성 가능해야 한다."""
    intent = OrderIntent(symbol=_SYMBOL, delta_weight=_DELTA_SELL, side="SELL")
    assert intent.side == "SELL"


def test_BUY_음수_delta_거부():
    """BUY side 에 음수 delta_weight 는 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="BUY"):
        OrderIntent(symbol=_SYMBOL, delta_weight=_DELTA_SELL, side="BUY")


def test_BUY_zero_delta_거부():
    """BUY side 에 delta_weight=0 은 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="BUY"):
        OrderIntent(symbol=_SYMBOL, delta_weight=_ZERO, side="BUY")


def test_SELL_양수_delta_거부():
    """SELL side 에 양수 delta_weight 는 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="SELL"):
        OrderIntent(symbol=_SYMBOL, delta_weight=_DELTA_BUY, side="SELL")


def test_SELL_zero_delta_거부():
    """SELL side 에 delta_weight=0 은 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="SELL"):
        OrderIntent(symbol=_SYMBOL, delta_weight=_ZERO, side="SELL")


def test_빈_symbol_거부():
    """빈 symbol 은 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="symbol"):
        OrderIntent(symbol="", delta_weight=_DELTA_BUY, side="BUY")


def test_frozen_변경_불가():
    """frozen dataclass 이므로 필드 변경 시 예외를 발생시킨다."""
    intent = OrderIntent(symbol=_SYMBOL, delta_weight=_DELTA_BUY, side="BUY")
    with pytest.raises(Exception):
        intent.side = "SELL"  # type: ignore[misc]


# ──────────────────────────────── RebalancePlan ───────────────────────────────

def test_빈_RebalancePlan_생성_성공():
    """빈 intents 로 생성 가능해야 한다."""
    plan = RebalancePlan(intents=())
    assert plan.intents == ()


def test_복수_OrderIntent_포함_생성_성공():
    """여러 OrderIntent 를 담은 RebalancePlan 생성 가능해야 한다."""
    buy = OrderIntent(symbol="AAPL", delta_weight=Decimal("0.2"), side="BUY")
    sell = OrderIntent(symbol="MSFT", delta_weight=Decimal("-0.1"), side="SELL")
    plan = RebalancePlan(intents=(buy, sell))
    assert len(plan.intents) == 2


def test_RebalancePlan_frozen_변경_불가():
    """frozen dataclass 이므로 intents 변경 시 예외를 발생시킨다."""
    plan = RebalancePlan(intents=())
    with pytest.raises(Exception):
        plan.intents = (OrderIntent(  # type: ignore[misc]
            symbol=_SYMBOL, delta_weight=_DELTA_BUY, side="BUY"
        ),)
