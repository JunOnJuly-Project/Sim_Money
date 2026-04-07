"""
SpearmanStrategy 단위 테스트 (TDD RED 단계).

WHY: SpearmanStrategy 는 SimilarityStrategy Protocol 의 두 번째 구현체다.
     WeightedSumStrategy 와 동일한 인터페이스(compute 메서드)를 보장해야만
     ADR-002 의 전략 교체 가능성(Strategy Pattern)이 실현된다.
     구현 전에 계약을 테스트로 고정해 인터페이스 회귀를 방지한다.
"""
from __future__ import annotations

import math

import pytest

from similarity.domain.spearman_strategy import SpearmanStrategy
from similarity.domain.spearman import spearman_correlation


# ---------------------------------------------------------------------------
# 케이스 1: SimilarityStrategy Protocol 호환 — compute 속성 존재
# ---------------------------------------------------------------------------

class TestSpearmanStrategy_프로토콜_호환:
    def test_SpearmanStrategy는_compute_메서드를_가진다(self):
        """WHY: SimilarityStrategy Protocol 은 compute(a, b) -> float 를 요구한다.
               hasattr 로 구조적 서브타이핑 충족 여부를 검증한다.
        """
        strategy = SpearmanStrategy()

        assert hasattr(strategy, "compute"), "compute 메서드가 없습니다"
        assert callable(strategy.compute), "compute 가 callable 이 아닙니다"


# ---------------------------------------------------------------------------
# 케이스 2: compute 결과가 spearman_correlation.value 와 일치
# ---------------------------------------------------------------------------

class TestSpearmanStrategy_compute_일치:
    def test_compute는_spearman_correlation_value와_일치한다(self):
        """WHY: SpearmanStrategy.compute 는 spearman_correlation 의 단순 래퍼다.
               value 가 동일해야 전략 교체 시 결과 일관성이 보장된다.
        """
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [10.0, 20.0, 30.0, 40.0, 50.0]

        strategy = SpearmanStrategy()
        score = strategy.compute(a, b)
        expected = spearman_correlation(a, b).value

        assert math.isclose(score, expected, abs_tol=1e-12), (
            f"compute({score}) 가 spearman_correlation.value({expected}) 와 다릅니다"
        )

    def test_compute는_부동소수_clamp_후_float를_반환한다(self):
        """WHY: compute 반환형은 float 이어야 하며 [-1, 1] 범위를 벗어나면 안 된다."""
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [5.0, 4.0, 3.0, 2.0, 1.0]

        strategy = SpearmanStrategy()
        score = strategy.compute(a, b)

        assert isinstance(score, float)
        assert -1.0 - 1e-9 <= score <= 1.0 + 1e-9


# ---------------------------------------------------------------------------
# 케이스 3: 결정론성 — 동일 입력 두 번 호출 시 동일 출력
# ---------------------------------------------------------------------------

class TestSpearmanStrategy_결정론성:
    def test_동일_입력_두_번_호출하면_동일_결과를_반환한다(self):
        """WHY: SimilarityStrategy 는 순수 함수여야 한다.
               상태를 가지거나 랜덤성이 있으면 재현 가능성이 깨진다.
        """
        a = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
        b = [2.0, 7.0, 1.0, 8.0, 2.0, 8.0, 1.0, 8.0]

        strategy = SpearmanStrategy()
        first = strategy.compute(a, b)
        second = strategy.compute(a, b)

        assert first == second, f"동일 입력에서 결과 불일치: {first} != {second}"

    def test_다른_인스턴스에서도_동일_입력이면_동일_결과를_반환한다(self):
        """WHY: frozen dataclass 인스턴스가 달라도 상태가 없으므로 결과가 동일해야 한다."""
        a = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
        b = [2.0, 7.0, 1.0, 8.0, 2.0, 8.0, 1.0, 8.0]

        strategy_1 = SpearmanStrategy()
        strategy_2 = SpearmanStrategy()

        assert strategy_1.compute(a, b) == strategy_2.compute(a, b)


# ---------------------------------------------------------------------------
# 케이스 4: 길이 검사 전파 — spearman_correlation 의 ValueError 가 그대로 전파
# ---------------------------------------------------------------------------

class TestSpearmanStrategy_길이_검사_전파:
    def test_길이_불일치_입력은_ValueError를_전파한다(self):
        """WHY: 입력 검증은 spearman_correlation 에 위임된다.
               strategy.compute 는 예외를 삼키지 않고 그대로 전파해야 한다.
        """
        a = [1.0, 2.0, 3.0]
        b = [1.0, 2.0]

        strategy = SpearmanStrategy()

        with pytest.raises(ValueError):
            strategy.compute(a, b)

    def test_길이_1_입력은_ValueError를_전파한다(self):
        """WHY: n=1 은 분산이 정의되지 않으므로 ValueError 가 전파되어야 한다."""
        strategy = SpearmanStrategy()

        with pytest.raises(ValueError):
            strategy.compute([1.0], [2.0])
