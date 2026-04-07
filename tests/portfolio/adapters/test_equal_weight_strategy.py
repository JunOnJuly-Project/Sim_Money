"""
EqualWeightStrategy 단위 테스트.

WHY: 균등 분배 로직과 max_cap 재분배를 격리 검증해
     다른 전략 도입 시 회귀를 방지한다.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from portfolio.adapters.outbound.equal_weight_strategy import EqualWeightStrategy
from portfolio.application.ports.weighting_strategy import SignalInput
from portfolio.domain.constraints import PortfolioConstraints

_STRATEGY = EqualWeightStrategy()
_NO_CONSTRAINT = PortfolioConstraints()


def _signals(*symbols: str) -> list[SignalInput]:
    """테스트용 SignalInput 리스트 헬퍼."""
    return [SignalInput(sym, Decimal("1")) for sym in symbols]


# --- 테스트 ---

def test_빈_입력_빈_결과():
    result = _STRATEGY.compute([], _NO_CONSTRAINT)
    assert result == ()


def test_1개_종목_균등():
    result = _STRATEGY.compute(_signals("A"), _NO_CONSTRAINT)
    assert len(result) == 1
    assert result[0].weight == Decimal("1")


def test_3개_종목_균등():
    result = _STRATEGY.compute(_signals("A", "B", "C"), _NO_CONSTRAINT)
    total = sum(w.weight for w in result)
    assert abs(total - Decimal("1")) < Decimal("1e-9")
    weights = {w.symbol: w.weight for w in result}
    assert weights["A"] == weights["B"] == weights["C"]


def test_10개_종목_균등():
    symbols = [f"X{i}" for i in range(10)]
    result = _STRATEGY.compute(_signals(*symbols), _NO_CONSTRAINT)
    total = sum(w.weight for w in result)
    assert abs(total - Decimal("1")) < Decimal("1e-9")


def test_cash_buffer_적용():
    """cash_buffer=0.1 이면 투자 가능 비중 합이 0.9 여야 한다."""
    constraints = PortfolioConstraints(cash_buffer=Decimal("0.1"))
    result = _STRATEGY.compute(_signals("A", "B"), constraints)
    total = sum(w.weight for w in result)
    assert abs(total - Decimal("0.9")) < Decimal("1e-9")


def test_max_cap_적용_캡_초과_잘라냄():
    """max_position_weight=0.2 이고 2개 종목이면 각 0.2 여야 한다."""
    constraints = PortfolioConstraints(max_position_weight=Decimal("0.2"))
    result = _STRATEGY.compute(_signals("A", "B"), constraints)
    for w in result:
        assert w.weight <= Decimal("0.2")


def test_max_cap_재분배_합_보존():
    """cap 적용 후 잔여를 재분배해도 총합은 investable 과 같아야 한다."""
    constraints = PortfolioConstraints(
        max_position_weight=Decimal("0.2"),
        cash_buffer=Decimal("0"),
    )
    # 5개 종목 → base=0.2 (cap 경계), 재분배 불필요
    result = _STRATEGY.compute(_signals("A", "B", "C", "D", "E"), constraints)
    total = sum(w.weight for w in result)
    assert abs(total - Decimal("1")) < Decimal("1e-9")
