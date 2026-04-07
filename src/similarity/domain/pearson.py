"""
Pearson 상관계수 계산 순수 함수.

WHY: Pearson ρ 는 M1 유사도 파이프라인에서 사용하는 유일한 선형 상관 측정 공식이다.
     numpy 의 np.corrcoef 를 래핑해 도메인 불변식 검증과 오류 처리를 중앙화한다.
     numpy 는 순수 수학 라이브러리이므로 domain 레이어에서 import 를 허용한다.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from similarity.domain.correlation import Correlation

# 상관계수 계산에 필요한 최소 관측 수.
# WHY: correlation.py 와 동일한 기준을 유지해 도메인 일관성을 보장한다.
_MIN_OBSERVATIONS: int = 2


def pearson_correlation(a: Sequence[float], b: Sequence[float]) -> Correlation:
    """두 수치 시퀀스의 Pearson 상관계수를 계산해 Correlation 값 객체로 반환한다.

    WHY: np.corrcoef 는 표준편차 0 상황에서 NaN 을 무음으로 반환한다.
         이 함수는 그 전에 명시적으로 ValueError 를 던져 후속 계산의 무음 오류를 차단한다.

    Args:
        a: 첫 번째 관측값 시퀀스
        b: 두 번째 관측값 시퀀스 (a 와 길이가 같아야 함)

    Returns:
        계산된 Correlation 값 객체

    Raises:
        ValueError: 길이 불일치, 최소 관측 수 미달, 표준편차 0 시
    """
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)

    _validate_inputs(arr_a, arr_b)

    rho = float(np.corrcoef(arr_a, arr_b)[0, 1])
    return Correlation(value=rho, n=len(arr_a))


def _validate_inputs(arr_a: np.ndarray, arr_b: np.ndarray) -> None:
    """입력 배열의 길이, 최소 관측 수, 표준편차를 검증한다."""
    _validate_lengths(arr_a, arr_b)
    _validate_min_observations(arr_a)
    _validate_std(arr_a, arr_b)


def _validate_lengths(arr_a: np.ndarray, arr_b: np.ndarray) -> None:
    """WHY: 길이가 다른 두 시리즈는 원소 대응이 불가능하다."""
    if len(arr_a) != len(arr_b):
        raise ValueError(
            f"두 시퀀스 길이가 달라야 합니다: {len(arr_a)} != {len(arr_b)}"
        )


def _validate_min_observations(arr_a: np.ndarray) -> None:
    """WHY: n < 2 이면 분산 자체가 정의되지 않는다."""
    if len(arr_a) < _MIN_OBSERVATIONS:
        raise ValueError(
            f"관측 수는 {_MIN_OBSERVATIONS} 이상이어야 합니다: {len(arr_a)!r}"
        )


def _validate_std(arr_a: np.ndarray, arr_b: np.ndarray) -> None:
    """WHY: 표준편차 0 인 시리즈는 Pearson 공식 분모가 0이 되어 NaN 이 발생한다.
           무음 실패 대신 명시적 오류로 호출자에게 알린다.
    """
    if np.std(arr_a) == 0 or np.std(arr_b) == 0:
        raise ValueError("표준편차 0 인 시리즈는 상관계수를 계산할 수 없습니다")
