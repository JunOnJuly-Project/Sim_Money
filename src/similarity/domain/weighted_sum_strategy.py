"""
M1 가중합 유사도 전략 구현.

WHY: ADR-002 에서 M1 단계 유사도 공식을 sign(ρ)·(w1·|ρ|+w2·shape+w3·stability) 로
     확정했다. 단순 |ρ| 만 쓰면 방향 정보가 소실되고, 코사인(shape) 을 추가하면
     스케일 불변 유사성을 포착하며, rolling 안정성(stability) 을 더하면 일시적
     상관 급변을 패널티화한다. sign(ρ) 를 곱해 방향을 최종 점수에 보존한다.
     이 공식은 SimilarityStrategy 포트의 첫 번째 구현체(WeightedSumStrategy) 로
     이후 Spearman/DTW/DCC-GARCH 등과 동일한 인터페이스로 교체 가능하다.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from similarity.domain.pearson import pearson_correlation

# 가중치 합 허용 오차 (부동소수점 표현 오차 수용).
# WHY: 1/3 + 1/3 + 1/3 은 1.0 과 ~1e-16 차이가 날 수 있다.
_WEIGHT_SUM_TOLERANCE: float = 1e-6

# rolling 상관계수 기본 윈도우 크기.
# WHY: 20일은 월별 거래일 수에 해당해 단기 안정성 측정에 충분하다.
_DEFAULT_ROLLING_WINDOW: int = 20

# stability 계산 시 rolling std 에 곱하는 계수.
# WHY: std 가 0.5 일 때 stability 가 0 이 되도록 2 를 선택해
#      "적당히 변동적인" 구간을 0~1 로 자연스럽게 매핑한다.
_STABILITY_COEFFICIENT: float = 2.0


@dataclass(frozen=True)
class SimilarityWeights:
    """가중합 공식의 세 가중치를 표현하는 불변 값 객체.

    WHY: 가중치를 별도 값 객체로 분리하면 검증 책임이 한 곳에 모이고,
         WeightedSumStrategy 의 생성자가 단순해진다.

    Attributes:
        w1: Pearson |ρ| 항 가중치
        w2: 코사인 유사도(shape) 항 가중치
        w3: rolling 안정성(stability) 항 가중치
    """

    w1: float
    w2: float
    w3: float

    def __post_init__(self) -> None:
        """생성 시 음수 여부와 합 = 1 불변식을 검증한다."""
        self._validate_non_negative()
        self._validate_sum()

    def _validate_non_negative(self) -> None:
        """WHY: 음수 가중치는 유사도 공식의 부호 의미를 훼손한다."""
        if any(w < 0 for w in (self.w1, self.w2, self.w3)):
            raise ValueError("가중치에 음수가 포함되어 있습니다: w1, w2, w3 는 모두 0 이상이어야 합니다")

    def _validate_sum(self) -> None:
        """WHY: 합이 1 이어야 가중합 점수가 [-1, 1] 내에 머문다."""
        total = self.w1 + self.w2 + self.w3
        if not math.isclose(total, 1.0, abs_tol=_WEIGHT_SUM_TOLERANCE):
            raise ValueError(
                f"가중치 합이 1.0 이어야 합니다 (허용 오차 {_WEIGHT_SUM_TOLERANCE}): 현재 합 = {total}"
            )


@dataclass(frozen=True)
class WeightedSumStrategy:
    """M1 가중합 유사도 전략.

    WHY: SimilarityStrategy 포트의 첫 번째 구현체로, ADR-002 에 정의된
         sign(ρ)·(w1·|ρ|+w2·shape+w3·stability) 공식을 실행한다.
         frozen dataclass 로 불변성을 보장해 공유 인스턴스에서도 사이드 이펙트가 없다.

    Attributes:
        weights: 세 항의 가중치
        rolling_window: rolling 상관계수 계산 윈도우 크기 (기본 20)
    """

    weights: SimilarityWeights
    rolling_window: int = _DEFAULT_ROLLING_WINDOW

    def compute(self, a: Sequence[float], b: Sequence[float]) -> float:
        """두 수치 시퀀스의 유사도 점수를 계산한다.

        Args:
            a: 첫 번째 관측값 시퀀스
            b: 두 번째 관측값 시퀀스 (a 와 길이가 같아야 함)

        Returns:
            유사도 점수 ∈ [-1, 1]

        Raises:
            ValueError: 길이 불일치, 관측 수 부족, 표준편차 0 시
        """
        # pearson_correlation 내부에서 길이/관측수/std 검증이 모두 수행된다.
        pearson = pearson_correlation(a, b)

        arr_a = np.asarray(a, dtype=float)
        arr_b = np.asarray(b, dtype=float)

        rho_avg = abs(pearson.value)
        cos_sim = _cosine_similarity(arr_a, arr_b)
        stability = _stability(arr_a, arr_b, self.rolling_window)

        raw = (
            self.weights.w1 * rho_avg
            + self.weights.w2 * cos_sim
            + self.weights.w3 * stability
        )
        score = pearson.sign() * raw

        # WHY: 가중치 합=1 · |ρ|,cos,stability ∈ [0,1] 이 모두 성립하면
        #      raw ∈ [0,1], score ∈ [-1,1] 이 수학적으로 보장된다.
        #      큰 범위 위반은 공식 회귀 버그이므로 assert 로 즉시 노출하고,
        #      clip 은 오직 부동소수점 미세 오차(1e-12 수준)만 흡수한다.
        assert -1.0 - 1e-9 <= score <= 1.0 + 1e-9, f"score 범위 위반: {score}"
        return float(np.clip(score, -1.0, 1.0))


def _cosine_similarity(arr_a: np.ndarray, arr_b: np.ndarray) -> float:
    """두 벡터의 코사인 유사도 절댓값을 반환한다.

    WHY: 코사인(shape) 항은 스케일에 무관한 방향 유사성을 측정한다.
         절댓값을 취해 크기(방향 정보)는 sign(ρ) 가 단독 처리하도록 분리한다.

    Returns:
        abs(dot(a, b) / (‖a‖·‖b‖)), 분모가 0 이면 0.0
    """
    dot = float(np.dot(arr_a, arr_b))
    norm_a = float(np.linalg.norm(arr_a))
    norm_b = float(np.linalg.norm(arr_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return abs(dot / (norm_a * norm_b))


def _rolling_pearson_std(
    arr_a: np.ndarray, arr_b: np.ndarray, window: int
) -> float | None:
    """rolling Pearson 상관계수의 표준편차를 반환한다.

    WHY: N < window 이면 rolling 상관계수를 신뢰할 수 없으므로 None 을 반환해
         호출자가 stability = 0 으로 처리하도록 한다.

    Returns:
        rolling 상관계수 std, N < window 이면 None
    """
    n = len(arr_a)
    if n < window:
        return None

    rolling_corrs = [
        float(np.corrcoef(arr_a[i : i + window], arr_b[i : i + window])[0, 1])
        for i in range(n - window + 1)
    ]

    return float(np.std(rolling_corrs))


def _stability(arr_a: np.ndarray, arr_b: np.ndarray, window: int) -> float:
    """rolling 상관계수 안정성을 [0, 1] 로 반환한다.

    WHY: rolling std 가 클수록 상관 관계가 불안정하므로 패널티를 부여한다.
         N < window 이면 rolling 상관계수 자체를 계산할 수 없으므로 0 으로 처리한다.

    Returns:
        clip(1 - 2·std, 0, 1), N < window 이면 0.0
    """
    rolling_std = _rolling_pearson_std(arr_a, arr_b, window)

    if rolling_std is None:
        return 0.0

    raw_stability = 1.0 - _STABILITY_COEFFICIENT * rolling_std
    return float(np.clip(raw_stability, 0.0, 1.0))
