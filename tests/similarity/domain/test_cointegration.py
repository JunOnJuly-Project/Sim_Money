"""
cointegration_test 순수 함수 단위 테스트 (TDD RED 단계).

WHY: Engle-Granger 2단계 공적분 검정은 statsmodels 없이 numpy 만으로
     수동 구현할 예정이다. 구현 전에 계약(입력 검증·수치 정확성·엣지 케이스)을
     테스트로 고정해 구현 회귀를 방지한다.
     공적분 시계열(공통 랜덤워크)과 독립 랜덤워크를 픽스처로 사용해
     p_value 의 방향성(낮음/높음)을 검증한다.
"""
from __future__ import annotations

import pytest
import numpy as np

from similarity.domain.cointegration import (
    CointegrationResult,
    cointegration_test,
)

# 결정론적 픽스처를 위한 고정 시드.
# WHY: 랜덤 픽스처는 단계·환경마다 결과가 달라 CI 를 불안정하게 만든다.
#      고정 시드로 재현 가능성을 보장한다.
_SEED: int = 42

# 공적분 검정이 의미있으려면 최소 30개 관측이 필요하다.
# WHY: ADF 검정의 점근 분포는 N 이 클수록 안정적이며, 30 미만은 검정력이
#      현저히 떨어진다. cointegration.py 의 _MIN_OBSERVATIONS 와 일치해야 한다.
_MIN_OBSERVATIONS: int = 30

# 공적분 시계열 길이 (N > _MIN_OBSERVATIONS 를 충분히 만족하는 값).
_N_COINT: int = 200


# ---------------------------------------------------------------------------
# 케이스 1: 공적분된 두 시계열 → p_value < 0.05
# ---------------------------------------------------------------------------

class TestCointegrationTest_공적분_시계열:
    def test_공통_랜덤워크_기반_시계열은_p_value가_0_05_미만이다(self):
        """WHY: y = x + 작은_노이즈 형태의 시계열은 잔차가 정상성을 가진다.
               ADF 검정은 정상 잔차를 높은 유의수준(낮은 p_value)으로 식별해야 한다.
               p_value < 0.05 는 5% 유의수준에서 공적분을 수용하는 표준 기준이다.
        """
        rng = np.random.default_rng(_SEED)

        # 공통 랜덤워크 생성
        random_walk = np.cumsum(rng.normal(0, 1, _N_COINT))
        # 작은 노이즈를 더해 y = x + ε (잔차가 정상성)
        noise = rng.normal(0, 0.1, _N_COINT)
        a = random_walk.tolist()
        b = (random_walk + noise).tolist()

        result = cointegration_test(a, b)

        assert result.p_value < 0.05, (
            f"공적분 시계열의 p_value 가 0.05 이상: {result.p_value:.4f}"
        )

    def test_공적분_결과는_CointegrationResult_인스턴스다(self):
        """WHY: 반환 타입이 CointegrationResult 임을 명시적으로 검증해
               향후 반환형 변경 시 즉시 실패하도록 고정한다.
        """
        rng = np.random.default_rng(_SEED)
        random_walk = np.cumsum(rng.normal(0, 1, _N_COINT))
        noise = rng.normal(0, 0.1, _N_COINT)
        a = random_walk.tolist()
        b = (random_walk + noise).tolist()

        result = cointegration_test(a, b)

        assert isinstance(result, CointegrationResult)


# ---------------------------------------------------------------------------
# 케이스 2: 독립 랜덤워크 두 개 → p_value > 0.1
# ---------------------------------------------------------------------------

class TestCointegrationTest_독립_랜덤워크:
    def test_독립_랜덤워크는_p_value가_0_1_초과다(self):
        """WHY: 두 독립 랜덤워크는 공통 확률 추세가 없으므로 잔차가 비정상성을 보인다.
               ADF 검정은 비정상 잔차를 높은 p_value 로 반환해야 한다.
               p_value > 0.1 은 공적분 없음을 지지하는 완화된 기준이다.
        """
        rng = np.random.default_rng(_SEED)

        walk_a = np.cumsum(rng.normal(0, 1, _N_COINT))
        walk_b = np.cumsum(rng.normal(0, 1, _N_COINT))

        result = cointegration_test(walk_a.tolist(), walk_b.tolist())

        assert result.p_value > 0.1, (
            f"독립 랜덤워크의 p_value 가 0.1 이하: {result.p_value:.4f}"
        )


# ---------------------------------------------------------------------------
# 케이스 3: 길이 불일치 → ValueError
# ---------------------------------------------------------------------------

class TestCointegrationTest_길이_불일치:
    def test_두_시퀀스_길이가_다르면_ValueError를_던진다(self):
        """WHY: 원소 대응이 불가능한 입력은 즉시 거부해 무음 계산 오류를 방지한다."""
        a = [1.0] * 50
        b = [1.0] * 49

        with pytest.raises(ValueError, match="길이"):
            cointegration_test(a, b)

    def test_한쪽이_빈_시퀀스면_ValueError를_던진다(self):
        """WHY: 빈 시퀀스는 길이 불일치(0 != N) 로 처리되어야 한다."""
        a: list[float] = []
        b = [1.0] * 50

        with pytest.raises(ValueError):
            cointegration_test(a, b)


# ---------------------------------------------------------------------------
# 케이스 4: 최소 관측 수 부족 (N < 30) → ValueError
# ---------------------------------------------------------------------------

class TestCointegrationTest_최소_관측_수:
    def test_관측_수가_30_미만이면_ValueError를_던진다(self):
        """WHY: N < _MIN_OBSERVATIONS 이면 ADF 검정 통계량의 점근 분포가 신뢰 불가다.
               명시적 ValueError 로 조용한 오진단을 방지한다.
        """
        a = list(range(1, _MIN_OBSERVATIONS))   # 길이 29
        b = list(range(1, _MIN_OBSERVATIONS))   # 길이 29

        with pytest.raises(ValueError, match="관측"):
            cointegration_test(a, b)

    def test_정확히_30개_관측은_통과한다(self):
        """WHY: 경계값(_MIN_OBSERVATIONS = 30) 은 허용되어야 한다.
               off-by-one 오류를 방지하기 위한 경계값 테스트.
        """
        rng = np.random.default_rng(_SEED)
        random_walk = np.cumsum(rng.normal(0, 1, _MIN_OBSERVATIONS))
        noise = rng.normal(0, 0.1, _MIN_OBSERVATIONS)
        a = random_walk.tolist()
        b = (random_walk + noise).tolist()

        # ValueError 없이 결과가 반환되어야 한다
        result = cointegration_test(a, b)
        assert isinstance(result, CointegrationResult)


# ---------------------------------------------------------------------------
# 케이스 5: OLS β 추정 정확성 — y = 2x + 노이즈 → beta ≈ 2.0
# ---------------------------------------------------------------------------

class TestCointegrationTest_OLS_베타_추정:
    def test_y_equals_2x_plus_noise_에서_beta가_2에_근접한다(self):
        """WHY: OLS 1단계는 y = α + β·x + ε 를 추정한다.
               y = 2x + 작은_노이즈 이면 β ≈ 2.0 이 되어야 수식이 올바르다.
               tol=0.1 은 합리적인 수치 허용 범위다.
        """
        rng = np.random.default_rng(_SEED)

        x = rng.uniform(1, 100, _N_COINT)
        noise = rng.normal(0, 0.5, _N_COINT)
        y = 2.0 * x + 5.0 + noise   # β=2, α=5

        result = cointegration_test(x.tolist(), y.tolist())

        assert abs(result.beta - 2.0) < 0.1, (
            f"beta 추정값 {result.beta:.4f} 이 2.0 에서 0.1 이상 벗어남"
        )

    def test_y_equals_x_plus_constant_에서_alpha가_상수에_근접한다(self):
        """WHY: OLS 절편 α 는 시계열 수준 차이를 흡수한다.
               y = x + 10 이면 α ≈ 10.0 이 되어야 한다.
        """
        rng = np.random.default_rng(_SEED)

        x = rng.uniform(1, 100, _N_COINT)
        noise = rng.normal(0, 0.5, _N_COINT)
        y = 1.0 * x + 10.0 + noise   # β=1, α=10

        result = cointegration_test(x.tolist(), y.tolist())

        assert abs(result.alpha - 10.0) < 1.0, (
            f"alpha 추정값 {result.alpha:.4f} 이 10.0 에서 1.0 이상 벗어남"
        )


# ---------------------------------------------------------------------------
# 케이스 6: 상수 시계열 → ValueError 또는 명시적 처리
# ---------------------------------------------------------------------------

class TestCointegrationTest_상수_시계열:
    def test_상수_시계열은_ValueError를_던진다(self):
        """WHY: 상수 시계열은 분산이 0이어서 OLS 회귀 계수를 정의할 수 없다.
               NaN/Inf 를 조용히 반환하는 대신 ValueError 를 던져야 한다.
        """
        a = [5.0] * _N_COINT
        b = [1.0, 2.0] * (_N_COINT // 2)   # b는 정상 시계열

        with pytest.raises(ValueError):
            cointegration_test(a, b)

    def test_둘_다_상수_시계열은_ValueError를_던진다(self):
        """WHY: 두 시계열 모두 상수이면 잔차가 0이 되어 ADF 검정을 수행할 수 없다."""
        a = [3.0] * _N_COINT
        b = [7.0] * _N_COINT

        with pytest.raises(ValueError):
            cointegration_test(a, b)


# ---------------------------------------------------------------------------
# 케이스 7: CointegrationResult 불변식 — p_value ∈ [0, 1]
# ---------------------------------------------------------------------------

class TestCointegrationResult_불변식:
    def test_p_value는_0과_1_사이에_있다(self):
        """WHY: p_value 는 확률이므로 수학적으로 [0, 1] 이어야 한다.
               구현 오류로 범위를 벗어나면 downstream 의 similarity score 가 깨진다.
        """
        rng = np.random.default_rng(_SEED)
        random_walk = np.cumsum(rng.normal(0, 1, _N_COINT))
        noise = rng.normal(0, 0.5, _N_COINT)
        a = random_walk.tolist()
        b = (random_walk + noise).tolist()

        result = cointegration_test(a, b)

        assert 0.0 <= result.p_value <= 1.0, (
            f"p_value 가 [0, 1] 범위 밖: {result.p_value}"
        )
