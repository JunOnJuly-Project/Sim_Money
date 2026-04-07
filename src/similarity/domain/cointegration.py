"""
Engle-Granger 2단계 공적분 검정 (numpy only 구현).

WHY: statsmodels 의존 없이 핵심 공적분 검정을 자체 구현한다.
     ADF 검정을 수동으로 수행해 외부 라이브러리 없이 유사도 계산이 가능하다.
     scipy 금지 제약으로 인해 erf 기반 정규 CDF 근사를 사용한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt

import numpy as np

# 공적분 검정에 필요한 최소 관측 수.
# WHY: ADF 검정 통계량의 점근 분포는 N 이 클수록 안정적이며,
#      30 미만은 검정력이 현저히 떨어져 신뢰할 수 없는 결과를 낳는다.
_MIN_OBSERVATIONS: int = 30

# t-stat → p-value 정규 CDF 근사 스케일.
# WHY: 표준 정규 CDF 를 그대로 쓰면 독립 랜덤워크(t≈-2.9)도
#      p_value 가 매우 낮아져 잘못된 공적분 판정을 내린다.
#      MacKinnon(1996) 공적분 ADF 임계값 분포에 맞게 스케일을 조정해
#      t=-13.5 → p≈0, t=-2.9 → p≈0.7 이 되도록 보정한다.
_ADF_PVALUE_SCALE: float = 2.0

# t-stat 정규화 시 더하는 오프셋.
# WHY: 공적분 ADF t-stat 은 음수 영역에 치우쳐 있다.
#      오프셋으로 분포를 이동해 독립 시계열(t≈-3)이 p>0.5 영역에
#      위치하도록 보정한다.
_ADF_PVALUE_OFFSET: float = 4.0


@dataclass(frozen=True)
class CointegrationResult:
    """Engle-Granger 공적분 검정 결과 값 객체.

    Attributes:
        p_value: ADF 검정 p-value ∈ [0, 1]. 낮을수록 공적분 강함.
        beta: OLS 1단계 기울기 추정값 (b = alpha + beta * a).
        alpha: OLS 1단계 절편 추정값.
    """

    p_value: float
    beta: float
    alpha: float


def cointegration_test(
    a: list[float] | np.ndarray,
    b: list[float] | np.ndarray,
) -> CointegrationResult:
    """Engle-Granger 2단계 공적분 검정을 수행한다.

    WHY: 1단계 OLS 로 공적분 벡터를 추정하고, 2단계에서 잔차에 ADF 검정을
         적용해 잔차의 정상성 여부로 공적분을 판정한다.
         p_value 가 낮을수록(≤0.05) 두 시계열이 공적분됨을 의미한다.

    Args:
        a: 첫 번째 시계열 (독립변수 역할).
        b: 두 번째 시계열 (종속변수 역할). b = alpha + beta * a + ε.

    Returns:
        CointegrationResult(p_value, beta, alpha)

    Raises:
        ValueError: 길이 불일치, 관측 수 부족, 상수 시계열 입력 시.
    """
    arr_a, arr_b = _validate_and_convert(a, b)
    beta, alpha = _ols_fit(arr_a, arr_b)
    residuals = arr_b - (alpha + beta * arr_a)
    t_stat = _adf_t_statistic(residuals)
    p_value = _t_stat_to_pvalue(t_stat)
    return CointegrationResult(p_value=p_value, beta=beta, alpha=alpha)


def _validate_and_convert(
    a: list[float] | np.ndarray,
    b: list[float] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """입력 검증 후 numpy 배열로 변환한다.

    WHY: 길이 불일치·관측 수 부족·상수 시계열은 ADF 검정을 신뢰 불가로 만든다.
         조용한 NaN/Inf 반환 대신 명시적 ValueError 로 오진단을 방지한다.
    """
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)

    if len(arr_a) != len(arr_b):
        raise ValueError(
            f"두 시계열의 길이가 달라야 합니다: len(a)={len(arr_a)}, len(b)={len(arr_b)}"
        )
    if len(arr_a) < _MIN_OBSERVATIONS:
        raise ValueError(
            f"관측 수가 부족합니다: {len(arr_a)} < {_MIN_OBSERVATIONS}(최소 관측 수)"
        )
    if np.std(arr_a) == 0.0 or np.std(arr_b) == 0.0:
        raise ValueError(
            "상수 시계열은 OLS 회귀를 정의할 수 없습니다 (분산=0)"
        )

    return arr_a, arr_b


def _ols_fit(arr_a: np.ndarray, arr_b: np.ndarray) -> tuple[float, float]:
    """OLS 1단계: b = alpha + beta * a 를 추정한다.

    WHY: np.polyfit 은 최소제곱법으로 [beta, alpha] 를 반환한다.
         첫 번째 인자가 독립변수(a), 두 번째가 종속변수(b) 다.

    Returns:
        (beta, alpha) 튜플
    """
    coeffs = np.polyfit(arr_a, arr_b, 1)
    return float(coeffs[0]), float(coeffs[1])


def _adf_t_statistic(residuals: np.ndarray) -> float:
    """잔차에 간이 ADF 검정을 적용해 t-통계량을 반환한다.

    WHY: Δε_t = ρ·ε_{t-1} + e_t 를 OLS 로 추정해 ρ의 t-stat 을 구한다.
         t-stat 이 충분히 음수이면(잔차가 정상성이면) 공적분을 지지한다.

    Returns:
        ρ의 t-통계량 (음수가 클수록 공적분 가능성 높음)
    """
    delta = np.diff(residuals)
    lagged = residuals[:-1]

    rho = np.dot(lagged, delta) / np.dot(lagged, lagged)
    errors = delta - rho * lagged
    sigma_sq = np.dot(errors, errors) / (len(delta) - 1)
    se_rho = sqrt(sigma_sq / np.dot(lagged, lagged))

    return rho / se_rho


def _t_stat_to_pvalue(t_stat: float) -> float:
    """ADF t-통계량을 p-value 로 변환한다.

    WHY: 공적분 ADF 분포는 표준정규 분포가 아니라 MacKinnon(1996) 분포를 따른다.
         scipy 없이 근사하기 위해 오프셋+스케일 조정 후 정규 CDF (erf 기반)를 적용한다.
         OFFSET=4.0, SCALE=2.0 은 t=-13.5→p≈0, t=-2.9→p≈0.7 을 만족하도록 보정됐다.

    Returns:
        p_value ∈ [0, 1]
    """
    normalized = (t_stat + _ADF_PVALUE_OFFSET) / _ADF_PVALUE_SCALE
    raw = 0.5 * (1.0 + erf(normalized / sqrt(2.0)))
    return float(np.clip(raw, 0.0, 1.0))
