"""
Correlation 값 객체 단위 테스트 (TDD RED 단계).

WHY: Correlation 은 유사도 점수 계산의 핵심 불변 객체다.
     도메인 불변식(범위, 관측 수, 유한성)을 구현 이전에 명세로 고정해
     구현 시 회귀를 즉시 탐지한다.
"""
from __future__ import annotations

import math
import pytest
from similarity.domain.correlation import Correlation


class TestCorrelation_정상_생성:
    def test_유효한_값과_관측수로_생성한다(self):
        """WHY: 정상 범위의 value 와 n 으로 생성 시 예외 없이 객체를 반환해야 한다."""
        corr = Correlation(value=0.85, n=30)

        assert corr.value == 0.85
        assert corr.n == 30

    def test_경계값_양의_1_로_생성한다(self):
        """WHY: 완전 양상관(1.0)은 유효한 경계값이므로 허용해야 한다."""
        corr = Correlation(value=1.0, n=2)

        assert corr.value == 1.0

    def test_경계값_음의_1_로_생성한다(self):
        """WHY: 완전 음상관(-1.0)은 유효한 경계값이므로 허용해야 한다."""
        corr = Correlation(value=-1.0, n=2)

        assert corr.value == -1.0


class TestCorrelation_범위_위반:
    def test_1_초과값은_ValueError_를_던진다(self):
        """WHY: |ρ| > 1 은 수학적으로 불가능한 값이므로 도메인 레벨에서 차단한다."""
        with pytest.raises(ValueError):
            Correlation(value=1.0 + 1e-8, n=10)

    def test_음의_1_미만값은_ValueError_를_던진다(self):
        """WHY: ρ < -1 도 동일하게 불가능한 범위다."""
        with pytest.raises(ValueError):
            Correlation(value=-1.0 - 1e-8, n=10)


class TestCorrelation_관측수_위반:
    def test_n이_1이면_ValueError_를_던진다(self):
        """WHY: 상관계수 계산은 최소 2개 관측값이 필요하다(자유도 = n-1 >= 1)."""
        with pytest.raises(ValueError):
            Correlation(value=0.5, n=1)

    def test_n이_0이면_ValueError_를_던진다(self):
        """WHY: 관측값이 없으면 상관계수 자체가 미정의다."""
        with pytest.raises(ValueError):
            Correlation(value=0.0, n=0)


class TestCorrelation_유한성:
    def test_NaN_값은_ValueError_를_던진다(self):
        """WHY: NaN 이 도메인 객체로 전파되면 후속 계산이 무음 오류를 낸다."""
        with pytest.raises(ValueError):
            Correlation(value=float("nan"), n=10)


class TestCorrelation_sign:
    def test_양수_값의_sign_은_1이다(self):
        """WHY: 부호는 상관 방향을 결정하는 유사도 공식의 핵심 요소다."""
        assert Correlation(value=0.7, n=20).sign() == 1

    def test_음수_값의_sign_은_음의_1이다(self):
        assert Correlation(value=-0.3, n=20).sign() == -1

    def test_0_값의_sign_은_0이다(self):
        assert Correlation(value=0.0, n=20).sign() == 0
