"""
WeightedSumStrategy 단위 테스트 (TDD RED 단계).

WHY: M1 공식 score = sign(ρ) · (w1·|ρ| + w2·shape + w3·stability) 는
     유사도 파이프라인의 핵심 계산 경로다.
     구현 전에 계약을 테스트로 고정해 회귀를 방지한다.

M1 정의:
  - shape    = abs(cosine_similarity(returns_a, returns_b))
  - stability = clip(1 - 2·std(rolling corr, window=20), 0, 1)
                N < 20 이면 stability = 0
  - score ∈ [-1, 1]
"""
from __future__ import annotations

import math

import pytest

from similarity.domain.weighted_sum_strategy import SimilarityWeights, WeightedSumStrategy


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _linspace(start: float, stop: float, n: int) -> list[float]:
    """n 개의 균등 간격 값을 반환한다."""
    if n == 1:
        return [start]
    step = (stop - start) / (n - 1)
    return [start + step * i for i in range(n)]


def _make_equal_weights() -> SimilarityWeights:
    """w1=w2=w3=1/3 인 균등 가중치를 반환한다."""
    return SimilarityWeights(w1=1 / 3, w2=1 / 3, w3=1 / 3)


# ---------------------------------------------------------------------------
# 케이스 1: SimilarityWeights 정상 생성
# ---------------------------------------------------------------------------

class TestSimilarityWeights_정상_생성:
    def test_합이_1인_가중치는_정상_생성된다(self):
        """WHY: w1+w2+w3 = 1.0 은 가중합 점수가 [-1, 1] 내에 머무는 필요조건이다."""
        weights = SimilarityWeights(w1=0.5, w2=0.3, w3=0.2)

        assert math.isclose(weights.w1 + weights.w2 + weights.w3, 1.0, abs_tol=1e-6)

    def test_극단적_단일_가중치도_정상_생성된다(self):
        """WHY: w1=1, w2=0, w3=0 은 순수 Pearson 점수를 의미하므로 유효한 설정이다."""
        weights = SimilarityWeights(w1=1.0, w2=0.0, w3=0.0)

        assert math.isclose(weights.w1, 1.0)
        assert weights.w2 == 0.0
        assert weights.w3 == 0.0


# ---------------------------------------------------------------------------
# 케이스 2: SimilarityWeights — 합 != 1 → ValueError
# ---------------------------------------------------------------------------

class TestSimilarityWeights_가중치_합_검증:
    def test_가중치_합이_1보다_크면_ValueError_를_던진다(self):
        """WHY: 합이 1 을 초과하면 가중합 점수가 [-1, 1] 범위를 벗어날 수 있다."""
        with pytest.raises(ValueError, match="합"):
            SimilarityWeights(w1=0.5, w2=0.4, w3=0.3)

    def test_가중치_합이_1보다_작으면_ValueError_를_던진다(self):
        """WHY: 합이 1 미만이면 가중합이 의도한 스케일을 잃는다."""
        with pytest.raises(ValueError, match="합"):
            SimilarityWeights(w1=0.2, w2=0.2, w3=0.2)

    def test_허용_오차_1e_6_이내는_정상_생성된다(self):
        """WHY: 부동소수점 표현 오차 1e-6 이내는 유효한 입력으로 허용한다."""
        # 1/3 + 1/3 + 1/3 은 부동소수점 상 1.0 과 미세 차이가 날 수 있다
        weights = SimilarityWeights(w1=1 / 3, w2=1 / 3, w3=1 / 3)

        assert math.isclose(weights.w1 + weights.w2 + weights.w3, 1.0, abs_tol=1e-6)


# ---------------------------------------------------------------------------
# 케이스 3: SimilarityWeights — 음수 → ValueError
# ---------------------------------------------------------------------------

class TestSimilarityWeights_음수_가중치_검증:
    def test_w1이_음수이면_ValueError_를_던진다(self):
        """WHY: 음수 가중치는 유사도 공식의 부호 의미를 훼손한다."""
        with pytest.raises(ValueError, match="음수"):
            SimilarityWeights(w1=-0.1, w2=0.6, w3=0.5)

    def test_w2가_음수이면_ValueError_를_던진다(self):
        with pytest.raises(ValueError, match="음수"):
            SimilarityWeights(w1=0.6, w2=-0.1, w3=0.5)

    def test_w3가_음수이면_ValueError_를_던진다(self):
        with pytest.raises(ValueError, match="음수"):
            SimilarityWeights(w1=0.6, w2=0.5, w3=-0.1)


# ---------------------------------------------------------------------------
# 케이스 4: 완전 양상관 (a = b) → score ≈ +1.0
# ---------------------------------------------------------------------------

class TestWeightedSumStrategy_완전_양상관:
    def test_완전_양상관_입력은_score_1에_수렴한다(self):
        """WHY: a == b 이면 ρ=1, shape=1, stability 는 최대여야 한다.
               최소 rolling_window(20) 를 확보해 stability 도 양수가 되도록 한다.
        """
        n = 60
        a = _linspace(1.0, float(n), n)
        b = list(a)  # 완전 동일
        weights = SimilarityWeights(w1=0.4, w2=0.3, w3=0.3)
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        score = strategy.compute(a, b)

        assert score > 0.9, f"완전 양상관 score 가 너무 낮음: {score}"

    def test_완전_양상관에서_score는_1_이하다(self):
        """WHY: score ∈ [-1, 1] 불변식 검증."""
        n = 60
        a = _linspace(1.0, float(n), n)
        b = list(a)
        weights = _make_equal_weights()
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        score = strategy.compute(a, b)

        assert score <= 1.0 + 1e-9


# ---------------------------------------------------------------------------
# 케이스 5: 완전 음상관 (b = -a) → score ≈ -1.0
# ---------------------------------------------------------------------------

class TestWeightedSumStrategy_완전_음상관:
    def test_완전_음상관_입력은_score_음수_1에_수렴한다(self):
        """WHY: b = -a 이면 ρ = -1, shape = abs(cos) = 1, stability 는 최대.
               sign(ρ) = -1 이므로 최종 score ≈ -1 이어야 한다.
        """
        n = 60
        a = _linspace(1.0, float(n), n)
        b = [-v for v in a]
        weights = SimilarityWeights(w1=0.4, w2=0.3, w3=0.3)
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        score = strategy.compute(a, b)

        assert score < -0.9, f"완전 음상관 score 가 너무 높음: {score}"

    def test_완전_음상관에서_score는_음수_1_이상이다(self):
        """WHY: score ∈ [-1, 1] 불변식 검증."""
        n = 60
        a = _linspace(1.0, float(n), n)
        b = [-v for v in a]
        weights = _make_equal_weights()
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        score = strategy.compute(a, b)

        assert score >= -1.0 - 1e-9


# ---------------------------------------------------------------------------
# 케이스 6: 길이 < rolling_window → stability = 0, score 계산은 됨
# ---------------------------------------------------------------------------

class TestWeightedSumStrategy_짧은_시리즈:
    def test_길이가_rolling_window_미만이면_stability_0으로_계산된다(self):
        """WHY: N=10, window=20 이면 rolling corr 을 계산할 수 없으므로 stability = 0.
               그러나 ρ, shape 는 계산 가능하므로 ValueError 없이 결과를 반환해야 한다.
        """
        n = 10
        a = _linspace(1.0, float(n), n)
        b = list(a)
        # w3 = 0 으로 두면 stability 가 0 이든 아니든 무관하게 score 를 예측 가능
        weights = SimilarityWeights(w1=0.6, w2=0.4, w3=0.0)
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        # 예외 없이 float 반환
        score = strategy.compute(a, b)

        assert isinstance(score, float)
        assert math.isfinite(score)

    def test_길이가_rolling_window_미만이면_w3_항은_0이다(self):
        """WHY: stability = 0 이면 w3·stability = 0 이므로 w3 기여가 사라진다.
               w3=1 인 경우와 w3=0 인 경우의 차이를 통해 stability=0 을 간접 검증한다.
        """
        n = 10
        a = _linspace(1.0, float(n), n)
        b = list(a)

        weights_with_w3 = SimilarityWeights(w1=0.5, w2=0.5, w3=0.0)
        weights_pure_w3 = SimilarityWeights(w1=0.0, w2=0.0, w3=1.0)

        strategy_no_w3 = WeightedSumStrategy(weights=weights_with_w3, rolling_window=20)
        strategy_pure_w3 = WeightedSumStrategy(weights=weights_pure_w3, rolling_window=20)

        score_no_w3 = strategy_no_w3.compute(a, b)
        score_pure_w3 = strategy_pure_w3.compute(a, b)

        # stability = 0 이면 sign(ρ)·w3·0 = 0
        assert math.isclose(score_pure_w3, 0.0, abs_tol=1e-9), (
            f"N<window 일 때 w3=1 score 는 0 이어야 하나 {score_pure_w3} 반환"
        )
        # w1=0.5, w2=0.5 케이스는 비제로여야 함
        assert not math.isclose(score_no_w3, 0.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# 케이스 7: sign 유지 — 음상관이면 score < 0
# ---------------------------------------------------------------------------

class TestWeightedSumStrategy_부호_보존:
    def test_음상관_데이터의_score_는_음수다(self):
        """WHY: sign(ρ) 를 곱하는 공식은 상관 방향을 score 에 보존해야 한다."""
        n = 40
        a = _linspace(1.0, float(n), n)
        # 단조 감소 → 음상관
        b = _linspace(float(n), 1.0, n)
        weights = _make_equal_weights()
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        score = strategy.compute(a, b)

        assert score < 0, f"음상관 데이터에서 score 가 양수: {score}"

    def test_양상관_데이터의_score_는_양수다(self):
        """WHY: 양상관이면 sign(ρ) = +1 이므로 score > 0 이어야 한다."""
        n = 40
        a = _linspace(1.0, float(n), n)
        b = _linspace(2.0, float(n) * 2, n)
        weights = _make_equal_weights()
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        score = strategy.compute(a, b)

        assert score > 0, f"양상관 데이터에서 score 가 음수: {score}"


# ---------------------------------------------------------------------------
# 케이스 8: w1=1, w2=0, w3=0 → score = sign(ρ)·|ρ|
# ---------------------------------------------------------------------------

class TestWeightedSumStrategy_순수_피어슨_가중치:
    def test_w1만_1이면_score_는_pearson_rho_와_같다(self):
        """WHY: 가중치 w1=1, w2=0, w3=0 은 WeightedSumStrategy 를 순수 Pearson 래퍼로 축퇴시킨다.
               score = sign(ρ)·|ρ| = ρ 이므로 직접 계산한 ρ 와 일치해야 한다.
        """
        import numpy as np

        n = 50
        rng = np.random.default_rng(seed=42)
        a = rng.standard_normal(n).tolist()
        b = rng.standard_normal(n).tolist()

        weights = SimilarityWeights(w1=1.0, w2=0.0, w3=0.0)
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        score = strategy.compute(a, b)

        expected_rho = float(np.corrcoef(a, b)[0, 1])
        assert math.isclose(score, expected_rho, abs_tol=1e-9), (
            f"w1=1 score({score}) 가 ρ({expected_rho}) 와 다름"
        )

    def test_w1만_1인_양상관_케이스에서_score_는_양수다(self):
        """WHY: 양상관에서 ρ > 0 → score = ρ > 0 임을 이중 검증한다."""
        n = 30
        a = _linspace(1.0, float(n), n)
        b = _linspace(2.0, float(n) + 1.0, n)
        weights = SimilarityWeights(w1=1.0, w2=0.0, w3=0.0)
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        score = strategy.compute(a, b)

        assert score > 0


# ---------------------------------------------------------------------------
# 케이스 9: 길이 불일치 → ValueError
# ---------------------------------------------------------------------------

class TestWeightedSumStrategy_길이_불일치:
    def test_두_시퀀스_길이가_다르면_ValueError_를_던진다(self):
        """WHY: 원소 대응이 불가능한 입력은 즉시 거부해야 한다."""
        a = [1.0, 2.0, 3.0]
        b = [1.0, 2.0]
        weights = _make_equal_weights()
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        with pytest.raises(ValueError):
            strategy.compute(a, b)

    def test_길이_1인_입력은_ValueError_를_던진다(self):
        """WHY: n=1 이면 Pearson 상관계수가 정의되지 않아 score 를 계산할 수 없다."""
        a = [1.0]
        b = [2.0]
        weights = _make_equal_weights()
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        with pytest.raises(ValueError):
            strategy.compute(a, b)

    def test_빈_시퀀스는_ValueError_를_던진다(self):
        """WHY: 관측값이 없으면 score 자체가 미정의다."""
        weights = _make_equal_weights()
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        with pytest.raises(ValueError):
            strategy.compute([], [])


# ---------------------------------------------------------------------------
# 케이스 10: 결정론적 — 동일 입력 두 번 호출 시 동일 출력
# ---------------------------------------------------------------------------

class TestWeightedSumStrategy_결정론성:
    def test_동일_입력_두_번_호출하면_동일_결과를_반환한다(self):
        """WHY: SimilarityStrategy 는 순수 함수여야 한다.
               상태를 가지거나 랜덤성이 있으면 재현 가능성이 깨진다.
        """
        n = 40
        a = _linspace(1.0, float(n), n)
        b = _linspace(2.0, float(n) * 1.5, n)
        weights = _make_equal_weights()
        strategy = WeightedSumStrategy(weights=weights, rolling_window=20)

        score_first = strategy.compute(a, b)
        score_second = strategy.compute(a, b)

        assert score_first == score_second, (
            f"동일 입력에서 결과 불일치: {score_first} != {score_second}"
        )

    def test_다른_전략_인스턴스도_동일_입력에서_동일_결과를_반환한다(self):
        """WHY: 인스턴스가 달라도 frozen dataclass 는 같은 상태를 보장한다."""
        n = 40
        a = _linspace(1.0, float(n), n)
        b = _linspace(2.0, float(n) * 1.5, n)
        weights = _make_equal_weights()

        strategy_1 = WeightedSumStrategy(weights=weights, rolling_window=20)
        strategy_2 = WeightedSumStrategy(weights=weights, rolling_window=20)

        assert strategy_1.compute(a, b) == strategy_2.compute(a, b)
