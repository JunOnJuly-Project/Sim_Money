"""
pearson_correlation 순수 함수 단위 테스트 (TDD RED 단계).

WHY: Pearson 상관계수는 M1 유사도 파이프라인의 유일한 ρ 계산원이다.
     수치 정확성, 경계 조건, 오류 전파를 구현 전에 명세로 고정한다.
"""
from __future__ import annotations

import math
import pytest
from similarity.domain.pearson import pearson_correlation


class TestPearsonCorrelation_완전_상관:
    def test_완전_양상관_데이터는_1을_반환한다(self):
        """WHY: 두 시리즈가 완전 선형 양의 관계이면 ρ = 1.0 이어야 한다."""
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [2.0, 4.0, 6.0, 8.0, 10.0]

        result = pearson_correlation(a, b)

        assert math.isclose(result.value, 1.0, abs_tol=1e-9)

    def test_완전_음상관_데이터는_음의_1을_반환한다(self):
        """WHY: 부호 반전된 선형 관계이면 ρ = -1.0 이어야 한다."""
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [5.0, 4.0, 3.0, 2.0, 1.0]

        result = pearson_correlation(a, b)

        assert math.isclose(result.value, -1.0, abs_tol=1e-9)

    def test_알려진_데이터셋_양상관은_1을_반환한다(self):
        """WHY: 정수 배수 관계는 완전 양상관이므로 ρ = 1.0 임을 수치로 검증한다."""
        a = [1, 2, 3, 4, 5]
        b = [2, 4, 6, 8, 10]

        result = pearson_correlation(a, b)

        assert math.isclose(result.value, 1.0, abs_tol=1e-9)

    def test_알려진_데이터셋_음상관은_음의_1을_반환한다(self):
        """WHY: 단조 감소 대칭 배열은 완전 음상관이므로 ρ = -1.0 임을 수치로 검증한다."""
        a = [1, 2, 3, 4, 5]
        b = [5, 4, 3, 2, 1]

        result = pearson_correlation(a, b)

        assert math.isclose(result.value, -1.0, abs_tol=1e-9)


class TestPearsonCorrelation_무상관:
    def test_직교_데이터는_0에_가까운_값을_반환한다(self):
        """WHY: 선형적으로 독립인 데이터 쌍은 ρ ≈ 0 이어야 한다.

        [1, -1, 1, -1, 1] 과 [1, 1, -1, -1, 0] 은 평균이 0이고 내적이 0이므로 무상관.
        """
        a = [1.0, -1.0, 1.0, -1.0, 1.0]
        b = [1.0, 1.0, -1.0, -1.0, 0.0]

        result = pearson_correlation(a, b)

        assert math.isclose(result.value, 0.0, abs_tol=1e-9)


class TestPearsonCorrelation_오류_조건:
    def test_길이_불일치_시_ValueError_를_던진다(self):
        """WHY: 길이가 다른 두 시리즈는 원소 대응이 불가능하므로 즉시 거부해야 한다."""
        a = [1.0, 2.0, 3.0]
        b = [1.0, 2.0]

        with pytest.raises(ValueError):
            pearson_correlation(a, b)

    def test_길이_1인_입력은_ValueError_를_던진다(self):
        """WHY: n=1 이면 분산이 정의되지 않아 상관계수를 계산할 수 없다."""
        a = [1.0]
        b = [2.0]

        with pytest.raises(ValueError):
            pearson_correlation(a, b)

    def test_빈_입력은_ValueError_를_던진다(self):
        """WHY: 관측값이 없으면 상관계수 자체가 미정의다."""
        a: list[float] = []
        b: list[float] = []

        with pytest.raises(ValueError):
            pearson_correlation(a, b)

    def test_표준편차_0인_시리즈는_ValueError_를_던진다(self):
        """WHY: 상수 시리즈는 표준편차가 0이므로 Pearson 공식 분모가 0이 된다.
               무음으로 NaN 을 반환하는 대신 ValueError 로 명시적으로 알린다.
        """
        a = [3.0, 3.0, 3.0, 3.0, 3.0]
        b = [1.0, 2.0, 3.0, 4.0, 5.0]

        with pytest.raises(ValueError, match="표준편차 0"):
            pearson_correlation(a, b)
