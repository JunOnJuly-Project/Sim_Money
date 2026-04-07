"""
WeightedSumStrategy 골든 회귀 테스트 (T-REG-01~05).

WHY: 미래 리팩터(알고리즘 최적화, numpy 버전 업, 내부 구조 변경 등) 후에도
     WeightedSumStrategy.compute() 의 수치 출력이 변하지 않음을 보장한다.
     테스트가 GREEN 이면 공식이 수치적으로 동일하다는 뜻이고,
     RED 가 되면 의도치 않은 회귀가 발생한 것이다.

기대값 산출 방법:
    최초 구현 시 실제 strategy.compute(a, b) 를 실행해 float 를 산출하고,
    그 값을 _EXPECTED_* 상수로 하드코딩했다.
    이후 이 상수와 실제 출력을 pytest.approx(abs=1e-6) 로 비교한다.

    WHY 1e-6: numpy 부동소수점 연산 오차 범위(~1e-15) 보다 훨씬 큰
              허용 오차를 주어 플랫폼·버전 차이를 흡수하되,
              공식이 실질적으로 달라졌을 때(>1e-6)는 탐지한다.

기본 설정:
    weights = SimilarityWeights(w1=0.5, w2=0.3, w3=0.2)
    rolling_window = 20 (T-REG-01~04)
    rolling_window = 20, N=15 (T-REG-05 — stability=0 유도)
"""
from __future__ import annotations

import pytest

from similarity.domain.weighted_sum_strategy import SimilarityWeights, WeightedSumStrategy
from tests.similarity.fixtures.golden_returns import (
    make_short_series,
    make_strongly_negative,
    make_strongly_positive,
    make_uncorrelated,
    make_weakly_positive,
)

# ---------------------------------------------------------------------------
# 모듈 스코프 공유 픽스처
# ---------------------------------------------------------------------------

_WEIGHTS = SimilarityWeights(w1=0.5, w2=0.3, w3=0.2)
_ROLLING_WINDOW = 20
_STRATEGY = WeightedSumStrategy(weights=_WEIGHTS, rolling_window=_ROLLING_WINDOW)

# ---------------------------------------------------------------------------
# 하드코딩된 골든 기대값
# WHY: 최초 구현 시 실제 compute() 출력으로 산출. 변경 금지.
#      변경이 필요하다면 ADR 또는 PR 주석으로 사유를 명시해야 한다.
# ---------------------------------------------------------------------------

_EXPECTED_REG_01: float = 0.9998390897986049   # 완전 양상관
_EXPECTED_REG_02: float = -0.9999999999999999  # 완전 음상관
_EXPECTED_REG_03: float = -0.11575363320321023  # 무상관 (|score| 작음)
_EXPECTED_REG_04: float = 0.8907751637897068   # 약 양상관
_EXPECTED_REG_05: float = -0.056409982565547766  # 짧은 시계열 (stability=0)

# pytest.approx 절대 허용 오차
_ABS_TOL: float = 1e-6


# ---------------------------------------------------------------------------
# T-REG-01: 완전 양상관
# ---------------------------------------------------------------------------


class TestGoldenRegression_T_REG_01_완전_양상관:
    """T-REG-01: a = linspace, b = 2*a + 상수 → score ≈ 0.9998"""

    def test_완전_양상관_score가_골든_기대값과_일치한다(self) -> None:
        """WHY: 완전 선형 양상관에서 ρ≈1, shape≈1, stability≈1 이므로
               score ≈ 0.5*1 + 0.3*1 + 0.2*1 = 1.0 에 수렴해야 한다.
               이 테스트는 그 수치가 리팩터 후에도 동일함을 보장한다.
        """
        a, b = make_strongly_positive()

        score = _STRATEGY.compute(a, b)

        assert score == pytest.approx(_EXPECTED_REG_01, abs=_ABS_TOL), (
            f"T-REG-01 골든 회귀 실패: 기대={_EXPECTED_REG_01}, 실제={score}"
        )

    def test_완전_양상관_score는_양수다(self) -> None:
        """WHY: 양상관 → sign(ρ)=+1 → score > 0 불변식 검증."""
        a, b = make_strongly_positive()

        score = _STRATEGY.compute(a, b)

        assert score > 0, f"T-REG-01: 양상관 score 가 양수여야 함. 실제={score}"

    def test_완전_양상관_score는_1_이하다(self) -> None:
        """WHY: score ∈ [-1, 1] 범위 불변식 검증."""
        a, b = make_strongly_positive()

        score = _STRATEGY.compute(a, b)

        assert score <= 1.0 + 1e-9, f"T-REG-01: score 가 1.0 을 초과. 실제={score}"


# ---------------------------------------------------------------------------
# T-REG-02: 완전 음상관
# ---------------------------------------------------------------------------


class TestGoldenRegression_T_REG_02_완전_음상관:
    """T-REG-02: b = -a → score ≈ -1.0"""

    def test_완전_음상관_score가_골든_기대값과_일치한다(self) -> None:
        """WHY: b = -a 이면 ρ=-1, sign=-1, shape≈1, stability≈1 이므로
               score = -1 * (0.5*1 + 0.3*1 + 0.2*1) ≈ -1.0 이 되어야 한다.
        """
        a, b = make_strongly_negative()

        score = _STRATEGY.compute(a, b)

        assert score == pytest.approx(_EXPECTED_REG_02, abs=_ABS_TOL), (
            f"T-REG-02 골든 회귀 실패: 기대={_EXPECTED_REG_02}, 실제={score}"
        )

    def test_완전_음상관_score는_음수다(self) -> None:
        """WHY: 음상관 → sign(ρ)=-1 → score < 0 불변식 검증."""
        a, b = make_strongly_negative()

        score = _STRATEGY.compute(a, b)

        assert score < 0, f"T-REG-02: 음상관 score 가 음수여야 함. 실제={score}"

    def test_완전_음상관_score는_음수_1_이상이다(self) -> None:
        """WHY: score ∈ [-1, 1] 범위 불변식 검증."""
        a, b = make_strongly_negative()

        score = _STRATEGY.compute(a, b)

        assert score >= -1.0 - 1e-9, f"T-REG-02: score 가 -1.0 미만. 실제={score}"


# ---------------------------------------------------------------------------
# T-REG-03: 무상관
# ---------------------------------------------------------------------------


class TestGoldenRegression_T_REG_03_무상관:
    """T-REG-03: 독립 정규 랜덤 → |score| < 0.2"""

    def test_무상관_score가_골든_기대값과_일치한다(self) -> None:
        """WHY: 독립 정규 분포에서 샘플링한 두 시계열은 이론적으로 ρ≈0 이므로
               |score| 가 작아야 한다. seed=42 고정으로 재현 가능한 '작은 값'을 고정한다.
        """
        a, b = make_uncorrelated()

        score = _STRATEGY.compute(a, b)

        assert score == pytest.approx(_EXPECTED_REG_03, abs=_ABS_TOL), (
            f"T-REG-03 골든 회귀 실패: 기대={_EXPECTED_REG_03}, 실제={score}"
        )

    def test_무상관_score의_절댓값은_0_2_미만이다(self) -> None:
        """WHY: 무상관 쌍에서 score 가 크면 공식이 잡음을 과대평가하는 것이다."""
        a, b = make_uncorrelated()

        score = _STRATEGY.compute(a, b)

        assert abs(score) < 0.2, f"T-REG-03: 무상관 |score| 가 너무 큼. 실제={score}"


# ---------------------------------------------------------------------------
# T-REG-04: 약 양상관
# ---------------------------------------------------------------------------


class TestGoldenRegression_T_REG_04_약_양상관:
    """T-REG-04: b = a + 0.5*noise → 중간 수준 양상관"""

    def test_약_양상관_score가_골든_기대값과_일치한다(self) -> None:
        """WHY: 신호(a) 에 노이즈가 절반 비율로 섞이면 ρ > 0 이지만 1 보다 작다.
               이 구조는 실제 페어 트레이딩 쌍의 전형적인 관계를 모사한다.
        """
        a, b = make_weakly_positive()

        score = _STRATEGY.compute(a, b)

        assert score == pytest.approx(_EXPECTED_REG_04, abs=_ABS_TOL), (
            f"T-REG-04 골든 회귀 실패: 기대={_EXPECTED_REG_04}, 실제={score}"
        )

    def test_약_양상관_score는_양수다(self) -> None:
        """WHY: b = a + noise 구조는 양상관이므로 score > 0 이어야 한다."""
        a, b = make_weakly_positive()

        score = _STRATEGY.compute(a, b)

        assert score > 0, f"T-REG-04: 약 양상관 score 가 양수여야 함. 실제={score}"

    def test_약_양상관_score는_무상관보다_크다(self) -> None:
        """WHY: 완전 양상관(T-REG-01) > 약 양상관(T-REG-04) > 무상관(T-REG-03)
               순서 불변식을 검증한다.
        """
        a_weak, b_weak = make_weakly_positive()
        a_uncorr, b_uncorr = make_uncorrelated()

        score_weak = _STRATEGY.compute(a_weak, b_weak)
        score_uncorr = _STRATEGY.compute(a_uncorr, b_uncorr)

        assert score_weak > score_uncorr, (
            f"T-REG-04: 약 양상관({score_weak}) 이 무상관({score_uncorr}) 보다 커야 함"
        )


# ---------------------------------------------------------------------------
# T-REG-05: 짧은 시계열 (stability = 0)
# ---------------------------------------------------------------------------


class TestGoldenRegression_T_REG_05_짧은_시계열:
    """T-REG-05: N=15 < rolling_window=20 → stability=0"""

    def test_짧은_시계열_score가_골든_기대값과_일치한다(self) -> None:
        """WHY: N < rolling_window 이면 _stability() 가 0 을 반환하므로
               w3 항 기여가 사라진다. 이 경계 조건의 수치를 고정한다.
        """
        a, b = make_short_series()

        score = _STRATEGY.compute(a, b)

        assert score == pytest.approx(_EXPECTED_REG_05, abs=_ABS_TOL), (
            f"T-REG-05 골든 회귀 실패: 기대={_EXPECTED_REG_05}, 실제={score}"
        )

    def test_짧은_시계열은_ValueError_없이_float를_반환한다(self) -> None:
        """WHY: N < window 이더라도 Pearson ρ 와 shape 는 계산 가능하므로
               예외 없이 float 가 반환되어야 한다.
        """
        a, b = make_short_series()

        score = _STRATEGY.compute(a, b)

        assert isinstance(score, float)

    def test_짧은_시계열_score는_범위_안에_있다(self) -> None:
        """WHY: score ∈ [-1, 1] 범위 불변식 — stability=0 이어도 성립해야 한다."""
        a, b = make_short_series()

        score = _STRATEGY.compute(a, b)

        assert -1.0 - 1e-9 <= score <= 1.0 + 1e-9, (
            f"T-REG-05: score 범위 위반. 실제={score}"
        )

    def test_짧은_시계열에서_w3만_1인_전략은_0을_반환한다(self) -> None:
        """WHY: stability=0 이면 sign(ρ)*w3*0=0 이므로,
               w3=1(w1=w2=0) 인 전략은 반드시 0 을 반환해야 한다.
               이를 통해 stability=0 인지를 간접적으로 확인한다.
        """
        a, b = make_short_series()
        weights_pure_w3 = SimilarityWeights(w1=0.0, w2=0.0, w3=1.0)
        strategy_pure_w3 = WeightedSumStrategy(weights=weights_pure_w3, rolling_window=_ROLLING_WINDOW)

        score = strategy_pure_w3.compute(a, b)

        assert score == pytest.approx(0.0, abs=1e-9), (
            f"T-REG-05: N<window 에서 w3=1 score 는 0 이어야 함. 실제={score}"
        )
