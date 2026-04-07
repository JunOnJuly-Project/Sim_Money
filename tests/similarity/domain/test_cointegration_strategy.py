"""
CointegrationStrategy 단위 테스트 (TDD RED 단계).

WHY: CointegrationStrategy 는 SimilarityStrategy 포트의 세 번째 구현체다.
     ADR-002 의 전략 교체 가능성(Strategy Pattern)이 실현되려면
     WeightedSumStrategy·SpearmanStrategy 와 동일한 compute(a, b) -> float
     인터페이스를 보장해야 한다.
     구현 전에 계약을 테스트로 고정해 인터페이스 회귀를 방지한다.

     similarity score = 1 - p_value ∈ [0, 1].
     공적분이 강할수록(p_value 가 낮을수록) score 가 1 에 근접한다.
"""
from __future__ import annotations

import pytest
import numpy as np

from similarity.domain.cointegration_strategy import CointegrationStrategy

# 결정론적 픽스처를 위한 고정 시드.
# WHY: 랜덤 픽스처는 단계·환경마다 결과가 달라 CI 를 불안정하게 만든다.
_SEED: int = 42

# 공적분 검정이 통계적으로 신뢰할 수 있는 충분한 길이.
_N: int = 200


# ---------------------------------------------------------------------------
# 케이스 1: SimilarityStrategy Protocol 호환성
# ---------------------------------------------------------------------------

class TestCointegrationStrategy_프로토콜_호환:
    def test_CointegrationStrategy는_compute_메서드를_가진다(self):
        """WHY: SimilarityStrategy Protocol 은 compute(a, b) -> float 를 요구한다.
               hasattr 로 구조적 서브타이핑 충족 여부를 검증한다.
        """
        strategy = CointegrationStrategy()

        assert hasattr(strategy, "compute"), "compute 메서드가 없습니다"
        assert callable(strategy.compute), "compute 가 callable 이 아닙니다"

    def test_CointegrationStrategy는_runtime_checkable_Protocol에_호환된다(self):
        """WHY: SimilarityStrategy 가 @runtime_checkable 로 선언되면
               isinstance 검사로 계약 이행 여부를 런타임에 확인할 수 있다.
               이 테스트는 Protocol 클래스가 실제로 import 가능하고
               CointegrationStrategy 가 구조적 서브타입임을 검증한다.
        """
        try:
            from similarity.domain.similarity_strategy import SimilarityStrategy  # type: ignore[import]
            strategy = CointegrationStrategy()
            assert isinstance(strategy, SimilarityStrategy), (
                "CointegrationStrategy 가 SimilarityStrategy Protocol 을 만족하지 않습니다"
            )
        except ImportError:
            # SimilarityStrategy Protocol 모듈이 아직 없으면 hasattr 검사로 대체
            strategy = CointegrationStrategy()
            assert hasattr(strategy, "compute")


# ---------------------------------------------------------------------------
# 케이스 2: 공적분 시계열 → compute() 결과 0.9 이상
# ---------------------------------------------------------------------------

class TestCointegrationStrategy_공적분_시계열:
    def test_공적분_시계열에서_compute가_0_9_이상을_반환한다(self):
        """WHY: 강한 공적분(p_value ≈ 0) 이면 score = 1 - p_value ≈ 1.0 이어야 한다.
               0.9 기준은 p_value < 0.1 에 대응하는 실용적 임계값이다.
        """
        rng = np.random.default_rng(_SEED)

        random_walk = np.cumsum(rng.normal(0, 1, _N))
        noise = rng.normal(0, 0.1, _N)   # 매우 작은 노이즈 → 강한 공적분
        a = random_walk.tolist()
        b = (random_walk + noise).tolist()

        strategy = CointegrationStrategy()
        score = strategy.compute(a, b)

        assert score >= 0.9, (
            f"공적분 시계열의 compute() 결과 {score:.4f} 가 0.9 미만"
        )

    def test_공적분_compute_결과는_float다(self):
        """WHY: compute 반환형은 float 이어야 SimilarityStrategy 계약을 충족한다."""
        rng = np.random.default_rng(_SEED)

        random_walk = np.cumsum(rng.normal(0, 1, _N))
        noise = rng.normal(0, 0.1, _N)
        a = random_walk.tolist()
        b = (random_walk + noise).tolist()

        strategy = CointegrationStrategy()
        score = strategy.compute(a, b)

        assert isinstance(score, float)


# ---------------------------------------------------------------------------
# 케이스 3: 독립 랜덤워크 → compute() 결과 0.5 이하
# ---------------------------------------------------------------------------

class TestCointegrationStrategy_독립_랜덤워크:
    def test_독립_랜덤워크에서_compute가_0_5_이하를_반환한다(self):
        """WHY: 독립 랜덤워크는 공적분이 없으므로 p_value 가 높고 score 가 낮아야 한다.
               score = 1 - p_value 이고 p_value > 0.5 이면 score < 0.5 이다.
               0.5 기준은 공적분 있음/없음의 실용적 구분선이다.
        """
        rng = np.random.default_rng(_SEED)

        walk_a = np.cumsum(rng.normal(0, 1, _N))
        walk_b = np.cumsum(rng.normal(0, 1, _N))

        strategy = CointegrationStrategy()
        score = strategy.compute(walk_a.tolist(), walk_b.tolist())

        assert score <= 0.5, (
            f"독립 랜덤워크의 compute() 결과 {score:.4f} 가 0.5 초과"
        )


# ---------------------------------------------------------------------------
# 케이스 4: score 범위 — [0, 1] 클리핑
# ---------------------------------------------------------------------------

class TestCointegrationStrategy_score_범위:
    def test_compute_결과는_0과_1_사이에_있다(self):
        """WHY: score = 1 - p_value 이고 p_value ∈ [0, 1] 이므로 score ∈ [0, 1].
               부동소수점 오차가 범위를 미세하게 벗어날 수 있으므로 clip 후 검증한다.
        """
        rng = np.random.default_rng(_SEED)

        random_walk = np.cumsum(rng.normal(0, 1, _N))
        noise = rng.normal(0, 0.5, _N)
        a = random_walk.tolist()
        b = (random_walk + noise).tolist()

        strategy = CointegrationStrategy()
        score = strategy.compute(a, b)

        assert 0.0 <= score <= 1.0, (
            f"score {score:.6f} 가 [0, 1] 범위 밖"
        )


# ---------------------------------------------------------------------------
# 케이스 5: 결정론성 — 동일 입력 → 동일 출력
# ---------------------------------------------------------------------------

class TestCointegrationStrategy_결정론성:
    def test_동일_입력_두_번_호출하면_동일_결과를_반환한다(self):
        """WHY: SimilarityStrategy 는 순수 함수여야 한다.
               상태나 랜덤성이 개입하면 백테스트 재현 가능성이 깨진다.
        """
        rng = np.random.default_rng(_SEED)

        random_walk = np.cumsum(rng.normal(0, 1, _N))
        noise = rng.normal(0, 0.3, _N)
        a = random_walk.tolist()
        b = (random_walk + noise).tolist()

        strategy = CointegrationStrategy()
        first = strategy.compute(a, b)
        second = strategy.compute(a, b)

        assert first == second, (
            f"동일 입력에서 결과 불일치: {first} != {second}"
        )

    def test_다른_인스턴스에서도_동일_입력이면_동일_결과를_반환한다(self):
        """WHY: frozen dataclass 인스턴스가 달라도 내부 상태가 없으므로 결과가 동일해야 한다."""
        rng = np.random.default_rng(_SEED)

        random_walk = np.cumsum(rng.normal(0, 1, _N))
        noise = rng.normal(0, 0.3, _N)
        a = random_walk.tolist()
        b = (random_walk + noise).tolist()

        strategy_1 = CointegrationStrategy()
        strategy_2 = CointegrationStrategy()

        assert strategy_1.compute(a, b) == strategy_2.compute(a, b)


# ---------------------------------------------------------------------------
# 케이스 6: 길이 불일치 에러 전파
# ---------------------------------------------------------------------------

class TestCointegrationStrategy_길이_불일치_에러_전파:
    def test_길이_불일치_입력은_ValueError를_전파한다(self):
        """WHY: 입력 검증은 cointegration_test 에 위임된다.
               strategy.compute 는 예외를 삼키지 않고 그대로 전파해야 한다.
        """
        a = [1.0] * 50
        b = [1.0] * 49

        strategy = CointegrationStrategy()

        with pytest.raises(ValueError):
            strategy.compute(a, b)

    def test_최소_관측_수_미달_입력은_ValueError를_전파한다(self):
        """WHY: N < 30 은 cointegration_test 에서 ValueError 를 던지며,
               compute 는 이를 그대로 전파해야 한다.
        """
        a = [float(i) for i in range(10)]
        b = [float(i) for i in range(10)]

        strategy = CointegrationStrategy()

        with pytest.raises(ValueError):
            strategy.compute(a, b)
