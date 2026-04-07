"""
PortfolioConstraints + CurrentPosition 도메인 값 객체 단위 테스트.
"""
import pytest
from decimal import Decimal

from portfolio.domain.constraints import PortfolioConstraints
from portfolio.domain.position import CurrentPosition

_SYMBOL = "AAPL"
_ZERO = Decimal("0")
_HALF = Decimal("0.5")
_ONE = Decimal("1")
_NEGATIVE = Decimal("-0.01")
_OVER = Decimal("1.01")


# ──────────────────────────────── PortfolioConstraints ────────────────────────

def test_기본값으로_생성_성공():
    """기본값(max=1, buffer=0, long_only=True)으로 생성 가능해야 한다."""
    c = PortfolioConstraints()
    assert c.max_position_weight == _ONE
    assert c.cash_buffer == _ZERO
    assert c.long_only is True


def test_유효한_값으로_생성_성공():
    """0~1 범위 값으로 정상 생성 가능해야 한다."""
    c = PortfolioConstraints(
        max_position_weight=_HALF,
        cash_buffer=Decimal("0.05"),
        long_only=False,
    )
    assert c.max_position_weight == _HALF


def test_max_position_weight_음수_거부():
    """max_position_weight < 0 이면 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="max_position_weight"):
        PortfolioConstraints(max_position_weight=_NEGATIVE)


def test_max_position_weight_1초과_거부():
    """max_position_weight > 1 이면 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="max_position_weight"):
        PortfolioConstraints(max_position_weight=_OVER)


def test_cash_buffer_음수_거부():
    """cash_buffer < 0 이면 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="cash_buffer"):
        PortfolioConstraints(cash_buffer=_NEGATIVE)


def test_cash_buffer_1초과_거부():
    """cash_buffer > 1 이면 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="cash_buffer"):
        PortfolioConstraints(cash_buffer=_OVER)


def test_frozen_변경_불가():
    """frozen dataclass 이므로 필드 변경 시 예외를 발생시킨다."""
    c = PortfolioConstraints()
    with pytest.raises(Exception):
        c.long_only = False  # type: ignore[misc]


# ──────────────────────────────── CurrentPosition ─────────────────────────────

def test_유효한_CurrentPosition_생성_성공():
    """정상 값으로 CurrentPosition 생성 가능해야 한다."""
    pos = CurrentPosition(symbol=_SYMBOL, quantity=Decimal("10"), market_value=Decimal("1000"))
    assert pos.symbol == _SYMBOL
    assert pos.quantity == Decimal("10")


def test_quantity_0_허용():
    """quantity=0 (포지션 없음)은 허용해야 한다."""
    pos = CurrentPosition(symbol=_SYMBOL, quantity=_ZERO, market_value=_ZERO)
    assert pos.quantity == _ZERO


def test_quantity_음수_거부():
    """quantity < 0 이면 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="quantity"):
        CurrentPosition(symbol=_SYMBOL, quantity=_NEGATIVE, market_value=_ZERO)


def test_빈_symbol_거부():
    """빈 symbol 은 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="symbol"):
        CurrentPosition(symbol="", quantity=_ZERO, market_value=_ZERO)
