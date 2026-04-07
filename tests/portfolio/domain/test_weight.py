"""
TargetWeight 도메인 값 객체 단위 테스트.
"""
import pytest
from decimal import Decimal

from portfolio.domain.weight import TargetWeight

_SYMBOL = "AAPL"
_WEIGHT_ZERO = Decimal("0")
_WEIGHT_HALF = Decimal("0.5")
_WEIGHT_ONE = Decimal("1")
_WEIGHT_NEGATIVE = Decimal("-0.01")
_WEIGHT_OVER = Decimal("1.01")


def test_유효한_TargetWeight_생성_성공():
    """정상 범위 weight 와 비공백 symbol 로 생성 가능해야 한다."""
    tw = TargetWeight(symbol=_SYMBOL, weight=_WEIGHT_HALF)
    assert tw.symbol == _SYMBOL
    assert tw.weight == _WEIGHT_HALF


def test_weight_0_경계값_허용():
    """weight=0 은 허용 범위 하한이다."""
    tw = TargetWeight(symbol=_SYMBOL, weight=_WEIGHT_ZERO)
    assert tw.weight == _WEIGHT_ZERO


def test_weight_1_경계값_허용():
    """weight=1 은 허용 범위 상한이다."""
    tw = TargetWeight(symbol=_SYMBOL, weight=_WEIGHT_ONE)
    assert tw.weight == _WEIGHT_ONE


def test_weight_음수_거부():
    """weight < 0 이면 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="weight"):
        TargetWeight(symbol=_SYMBOL, weight=_WEIGHT_NEGATIVE)


def test_weight_1초과_거부():
    """weight > 1 이면 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="weight"):
        TargetWeight(symbol=_SYMBOL, weight=_WEIGHT_OVER)


def test_빈_symbol_거부():
    """빈 문자열 symbol 은 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="symbol"):
        TargetWeight(symbol="", weight=_WEIGHT_HALF)


def test_공백만_있는_symbol_거부():
    """공백만 있는 symbol 은 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError, match="symbol"):
        TargetWeight(symbol="   ", weight=_WEIGHT_HALF)


def test_frozen_변경_불가():
    """frozen dataclass 이므로 필드 변경 시 FrozenInstanceError 를 발생시킨다."""
    tw = TargetWeight(symbol=_SYMBOL, weight=_WEIGHT_HALF)
    with pytest.raises(Exception):
        tw.weight = _WEIGHT_ONE  # type: ignore[misc]
