"""
AdjustedPrice, LogReturn 도메인 값 객체 테스트.

WHY: 수정주가와 로그수익률은 금융 계산의 기반이므로
     유효하지 않은 입력(음수, NaN, Inf)을 도메인 레벨에서 차단한다.
"""
import math
import pytest
from decimal import Decimal
from market_data.domain.adjusted_price import AdjustedPrice
from market_data.domain.log_return import LogReturn


def test_AdjustedPrice_는_양수만_허용():
    AdjustedPrice(value=Decimal("100"))
    with pytest.raises(ValueError):
        AdjustedPrice(value=Decimal("0"))
    with pytest.raises(ValueError):
        AdjustedPrice(value=Decimal("-1"))


def test_AdjustedPrice_from_float():
    p = AdjustedPrice.from_float(123.45)
    assert p.value == Decimal("123.45")


def test_AdjustedPrice_NaN_거부():
    with pytest.raises(ValueError):
        AdjustedPrice.from_float(float("nan"))


def test_AdjustedPrice_Inf_거부():
    with pytest.raises(ValueError):
        AdjustedPrice.from_float(float("inf"))


def test_LogReturn_from_prices_10퍼센트_상승():
    prev = AdjustedPrice.from_float(100.0)
    curr = AdjustedPrice.from_float(110.0)
    r = LogReturn.from_prices(prev, curr)
    assert math.isclose(r.value, math.log(1.1), rel_tol=1e-9)


def test_LogReturn_0수익률():
    prev = AdjustedPrice.from_float(100.0)
    curr = AdjustedPrice.from_float(100.0)
    r = LogReturn.from_prices(prev, curr)
    assert r.value == 0.0


def test_LogReturn_음수수익률():
    prev = AdjustedPrice.from_float(100.0)
    curr = AdjustedPrice.from_float(90.0)
    r = LogReturn.from_prices(prev, curr)
    assert r.value < 0
    assert math.isclose(r.value, math.log(0.9), rel_tol=1e-9)


def test_LogReturn_NaN_거부():
    with pytest.raises(ValueError):
        LogReturn(value=float("nan"))


def test_LogReturn_Inf_거부():
    with pytest.raises(ValueError):
        LogReturn(value=float("inf"))


def test_LogReturn_등가성():
    r1 = LogReturn(value=0.05)
    r2 = LogReturn(value=0.05)
    assert r1 == r2
    assert hash(r1) == hash(r2)
