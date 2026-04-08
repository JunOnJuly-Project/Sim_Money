"""
ScoreWeightedStrategy 단위 테스트.

WHY: score 비례 분배 로직과 edge case (음수·0합·캡·버퍼)를 격리 검증해
     EqualWeightStrategy 와의 동작 차이를 회귀 방지한다.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from portfolio.adapters.outbound.score_weighted_strategy import ScoreWeightedStrategy
from portfolio.application.ports.weighting_strategy import SignalInput
from portfolio.domain.constraints import PortfolioConstraints

_STRATEGY = ScoreWeightedStrategy()
_NO_CONSTRAINT = PortfolioConstraints()
_TOL = Decimal("1e-9")


def _sig(symbol: str, score: str) -> SignalInput:
    """테스트용 SignalInput 헬퍼."""
    return SignalInput(symbol, Decimal(score))


# ── 빈 입력 ─────────────────────────────────────────────────────────────────

def test_빈_입력_빈_결과():
    assert _STRATEGY.compute([], _NO_CONSTRAINT) == ()


# ── 균등 score → 균등 비중 ───────────────────────────────────────────────────

def test_균등_score_3개_균등_비중():
    """score 가 모두 같으면 EqualWeight 와 결과가 동일해야 한다."""
    signals = [_sig("A", "1"), _sig("B", "1"), _sig("C", "1")]
    result = _STRATEGY.compute(signals, _NO_CONSTRAINT)
    weights = {w.symbol: w.weight for w in result}
    expected = Decimal("1") / Decimal("3")
    assert abs(weights["A"] - expected) < _TOL
    assert weights["A"] == weights["B"] == weights["C"]


# ── 차등 score → 비율 가중치 ─────────────────────────────────────────────────

def test_차등_score_비율_가중치():
    """score 가 1:3 이면 weight 도 1:3 비율이어야 한다."""
    signals = [_sig("A", "1"), _sig("B", "3")]
    result = _STRATEGY.compute(signals, _NO_CONSTRAINT)
    weights = {w.symbol: w.weight for w in result}
    ratio = weights["B"] / weights["A"]
    assert abs(ratio - Decimal("3")) < _TOL


def test_차등_score_총합_investable():
    """score 차등 시 비중 합은 investable(=1) 이어야 한다."""
    signals = [_sig("A", "2"), _sig("B", "3"), _sig("C", "5")]
    result = _STRATEGY.compute(signals, _NO_CONSTRAINT)
    total = sum(w.weight for w in result)
    assert abs(total - Decimal("1")) < _TOL


# ── score 합 0 → EqualWeight 폴백 ────────────────────────────────────────────

def test_score_합_0_균등_폴백():
    """score 가 모두 0 이면 균등 분배로 폴백해야 한다."""
    signals = [_sig("A", "0"), _sig("B", "0")]
    result = _STRATEGY.compute(signals, _NO_CONSTRAINT)
    weights = {w.symbol: w.weight for w in result}
    assert abs(weights["A"] - Decimal("0.5")) < _TOL
    assert abs(weights["B"] - Decimal("0.5")) < _TOL


# ── 음수 score → ValueError ──────────────────────────────────────────────────

def test_음수_score_ValueError():
    """음수 score 가 있으면 ValueError 를 발생시켜야 한다."""
    signals = [_sig("A", "1"), _sig("B", "-0.1")]
    with pytest.raises(ValueError, match="score 는 0 이상이어야 합니다"):
        _STRATEGY.compute(signals, _NO_CONSTRAINT)


# ── cash_buffer 적용 ─────────────────────────────────────────────────────────

def test_cash_buffer_적용_합_검증():
    """cash_buffer=0.2 이면 비중 합은 0.8 이어야 한다."""
    constraints = PortfolioConstraints(cash_buffer=Decimal("0.2"))
    signals = [_sig("A", "1"), _sig("B", "1")]
    result = _STRATEGY.compute(signals, constraints)
    total = sum(w.weight for w in result)
    assert abs(total - Decimal("0.8")) < _TOL


# ── max_position_weight 캡 ───────────────────────────────────────────────────

def test_max_position_weight_캡_적용():
    """score 가 극단적으로 쏠려도 max_position_weight 를 초과할 수 없다."""
    constraints = PortfolioConstraints(max_position_weight=Decimal("0.4"))
    # score 가 99:1 이므로 raw weight ≈ 0.99 이나 캡으로 0.4 에 잘려야 한다
    signals = [_sig("A", "99"), _sig("B", "1")]
    result = _STRATEGY.compute(signals, constraints)
    for w in result:
        assert w.weight <= Decimal("0.4")


def test_max_position_weight_초과_잘라냄_재분배_없음():
    """캡 초과분은 버려지므로 총합이 investable 보다 작을 수 있다."""
    constraints = PortfolioConstraints(max_position_weight=Decimal("0.3"))
    signals = [_sig("A", "9"), _sig("B", "1")]
    result = _STRATEGY.compute(signals, constraints)
    # A raw ≈ 0.9 → 캡 0.3, B raw ≈ 0.1 → 유지
    # 합 = 0.3 + 0.1 = 0.4 < 1.0
    total = sum(w.weight for w in result)
    assert total < Decimal("1")
