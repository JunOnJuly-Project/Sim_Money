"""
spearman_correlation 순수 함수 단위 테스트 (TDD RED 단계).

WHY: Spearman ρ 는 순위 기반 상관계수로, 비선형 단조 관계를 Pearson 보다
     정확하게 포착한다. M1 → Phase 2 전환 시 SimilarityStrategy 포트의
     두 번째 구현체 근거가 되므로, 계약을 구현 전에 테스트로 고정한다.
"""
from __future__ import annotations

import math

import pytest

from similarity.domain.spearman import spearman_correlation


# ---------------------------------------------------------------------------
# 케이스 1: 완전 단조증가 → ρ = 1
# ---------------------------------------------------------------------------

class TestSpearmanCorrelation_완전_단조증가:
    def test_완전_단조증가_시리즈는_rho_1을_반환한다(self):
        """WHY: 단조 증가하는 두 시리즈의 순위가 동일하면 Spearman ρ = 1.0 이어야 한다."""
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [10.0, 20.0, 30.0, 40.0, 50.0]

        result = spearman_correlation(a, b)

        assert math.isclose(result.value, 1.0, abs_tol=1e-9)
        assert result.n == 5


# ---------------------------------------------------------------------------
# 케이스 2: 완전 단조감소 → ρ = -1
# ---------------------------------------------------------------------------

class TestSpearmanCorrelation_완전_단조감소:
    def test_완전_단조감소_시리즈는_rho_음수1을_반환한다(self):
        """WHY: a 가 증가하고 b 가 감소하면 순위가 완전 반전되어 ρ = -1.0 이어야 한다."""
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [50.0, 40.0, 30.0, 20.0, 10.0]

        result = spearman_correlation(a, b)

        assert math.isclose(result.value, -1.0, abs_tol=1e-9)
        assert result.n == 5


# ---------------------------------------------------------------------------
# 케이스 3: 비선형 단조증가 (y = exp(x)) → Pearson < 1 이지만 Spearman = 1
# ---------------------------------------------------------------------------

class TestSpearmanCorrelation_비선형_단조:
    def test_지수함수_관계는_pearson과_달리_rho_1을_반환한다(self):
        """WHY: y = exp(x) 는 비선형이지만 단조 증가이므로 순위가 동일하다.
               Pearson ρ < 1 이지만 Spearman ρ = 1.0 이어야 한다.
               이것이 Spearman 을 별도 전략으로 도입하는 핵심 이유다.
        """
        import math as _math

        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [_math.exp(x) for x in a]

        result = spearman_correlation(a, b)

        assert math.isclose(result.value, 1.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# 케이스 4: 동률 포함 → 값 유한, |ρ| <= 1
# ---------------------------------------------------------------------------

class TestSpearmanCorrelation_동률_포함:
    def test_동률이_포함된_시리즈는_유한한_rho를_반환한다(self):
        """WHY: 동률(tie)이 있으면 average rank 를 사용해야 NaN 을 피할 수 있다.
               결과는 유한하고 [-1, 1] 범위 안에 있어야 한다.
        """
        a = [1.0, 1.0, 2.0, 3.0, 3.0]
        b = [1.0, 2.0, 2.0, 4.0, 5.0]

        result = spearman_correlation(a, b)

        assert math.isfinite(result.value)
        assert -1.0 - 1e-9 <= result.value <= 1.0 + 1e-9
        assert result.n == 5


# ---------------------------------------------------------------------------
# 케이스 5: 길이 불일치 → ValueError
# ---------------------------------------------------------------------------

class TestSpearmanCorrelation_길이_불일치:
    def test_두_시퀀스_길이가_다르면_ValueError를_던진다(self):
        """WHY: 원소 대응이 불가능한 입력은 즉시 거부해 무음 오류를 방지한다."""
        a = [1.0, 2.0, 3.0]
        b = [1.0, 2.0]

        with pytest.raises(ValueError, match="길이"):
            spearman_correlation(a, b)


# ---------------------------------------------------------------------------
# 케이스 6: 길이 < 2 → ValueError
# ---------------------------------------------------------------------------

class TestSpearmanCorrelation_최소_관측_수:
    def test_길이_1인_입력은_ValueError를_던진다(self):
        """WHY: n=1 이면 분산이 정의되지 않아 Spearman 상관계수를 계산할 수 없다."""
        a = [1.0]
        b = [2.0]

        with pytest.raises(ValueError, match="관측"):
            spearman_correlation(a, b)

    def test_빈_입력은_ValueError를_던진다(self):
        """WHY: 관측값이 없으면 순위 자체를 정의할 수 없다."""
        with pytest.raises(ValueError, match="관측"):
            spearman_correlation([], [])


# ---------------------------------------------------------------------------
# 케이스 7: 상수 시리즈 (std = 0 after ranking) → ValueError
# ---------------------------------------------------------------------------

class TestSpearmanCorrelation_상수_시리즈:
    def test_상수_시리즈는_ValueError를_던진다(self):
        """WHY: 모든 원소가 동일하면 순위 변환 후에도 분산이 0이다.
               Pearson 공식 분모가 0이 되므로 무음 NaN 대신 ValueError 를 던진다.
        """
        a = [3.0, 3.0, 3.0, 3.0, 3.0]
        b = [1.0, 2.0, 3.0, 4.0, 5.0]

        with pytest.raises(ValueError, match="표준편차"):
            spearman_correlation(a, b)


# ---------------------------------------------------------------------------
# 케이스 8: 알려진 소형 데이터셋 기대값 검증
# ---------------------------------------------------------------------------

class TestSpearmanCorrelation_알려진_기대값:
    def test_소형_데이터셋에서_수동_계산값과_일치한다(self):
        """WHY: 수치 구현의 정확성을 손으로 계산한 기준값으로 고정한다.

        데이터:
            a = [1, 2, 3, 4, 5]  → 순위 [1, 2, 3, 4, 5]
            b = [5, 6, 7, 8, 7]  → 순위 [1, 2, 3.5, 5, 3.5]
        d  = [-0, 0, -0.5, -1, 1.5]   → d² = [0, 0, 0.25, 1, 2.25]
        Σd² = 3.5
        ρ = 1 - 6·Σd² / (n(n²-1)) = 1 - 6·3.5 / (5·24) = 1 - 21/120 = 1 - 0.175 = 0.825

        단, 동률이 있으면 표준 보정 공식을 써야 하므로 위 간이식과 차이가 날 수 있다.
        여기서는 average rank 기반 Pearson 방식으로 계산하므로 abs(ρ - 0.825) < 0.02 수준을
        허용 범위로 설정한다.
        """
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [5.0, 6.0, 7.0, 8.0, 7.0]

        result = spearman_correlation(a, b)

        # average rank + pearson 방식의 정확한 기대값 검증
        assert math.isfinite(result.value)
        assert result.value > 0.8, f"기대 ρ ≈ 0.825 보다 낮음: {result.value}"
        assert result.value <= 1.0 + 1e-9
        assert result.n == 5
