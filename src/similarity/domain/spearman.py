"""
Spearman 순위 상관계수 계산 순수 함수.

WHY: Pearson ρ 는 선형 관계만 측정하지만, Spearman ρ 는 순위 변환을 먼저 수행해
     비선형 단조 관계(예: y = exp(x)) 도 정확하게 포착한다.
     Phase 2 전략 교체(ADR-002)를 위해 Pearson 과 동일한 Correlation 값 객체를 반환한다.

     numpy 의 argsort 기반 average-rank 변환 후 Pearson 공식을 재사용한다.
     scipy 없이 numpy 만 사용해 의존성 최소화 원칙을 유지한다.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from similarity.domain.correlation import Correlation
from similarity.domain.pearson import pearson_correlation

# 상관계수 계산에 필요한 최소 관측 수.
# WHY: pearson.py 와 동일한 상수를 재선언해 도메인 일관성을 유지한다.
_MIN_OBSERVATIONS: int = 2


def spearman_correlation(a: Sequence[float], b: Sequence[float]) -> Correlation:
    """두 수치 시퀀스의 Spearman 순위 상관계수를 계산해 Correlation 값 객체로 반환한다.

    WHY: 순위 변환 후 Pearson 공식을 재사용해 코드 중복 없이 Spearman ρ 를 구한다.
         pearson_correlation 이 길이/관측수/표준편차 검증을 담당하므로,
         이 함수는 순위 변환만 추가로 수행한다.

    Args:
        a: 첫 번째 관측값 시퀀스
        b: 두 번째 관측값 시퀀스 (a 와 길이가 같아야 함)

    Returns:
        계산된 Correlation 값 객체 (n 은 원본 관측 수)

    Raises:
        ValueError: 길이 불일치, 최소 관측 수 미달, 표준편차 0 시
    """
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)

    _validate_lengths(arr_a, arr_b)
    _validate_min_observations(arr_a)

    rank_a = _average_rank(arr_a)
    rank_b = _average_rank(arr_b)

    # pearson_correlation 에 순위 배열을 전달해 Spearman ρ 를 계산한다.
    # WHY: 순위 배열에 표준편차 검사가 필요하며, pearson_correlation 이 이를 담당한다.
    result = pearson_correlation(rank_a.tolist(), rank_b.tolist())

    # n 은 원본 관측 수를 보존한다.
    return Correlation(value=result.value, n=len(arr_a))


def _average_rank(arr: np.ndarray) -> np.ndarray:
    """1차원 배열을 average-rank 배열로 변환한다.

    WHY: 동률(tie)이 있을 때 단순 argsort 는 임의 순서를 부여해 결과를 왜곡한다.
         average rank 는 동률 원소에 동일한 평균 순위를 부여해 NaN 없이 안정적이다.

    Args:
        arr: 순위를 계산할 1차원 numpy 배열

    Returns:
        1 기반 average-rank 배열 (동률은 평균 순위 공유)
    """
    n = len(arr)
    order = np.argsort(arr, kind="stable")

    rank = np.empty(n, dtype=float)
    rank[order] = np.arange(1, n + 1, dtype=float)

    # 동률 그룹을 찾아 해당 위치의 순위를 평균으로 교체한다.
    sorted_arr = arr[order]
    i = 0
    while i < n:
        j = i + 1
        while j < n and sorted_arr[j] == sorted_arr[i]:
            j += 1

        if j > i + 1:
            avg = float(np.mean(np.arange(i + 1, j + 1, dtype=float)))
            rank[order[i:j]] = avg

        i = j

    return rank


def _validate_lengths(arr_a: np.ndarray, arr_b: np.ndarray) -> None:
    """WHY: 길이가 다른 두 시리즈는 원소 대응이 불가능하다."""
    if len(arr_a) != len(arr_b):
        raise ValueError(
            f"두 시퀀스 길이가 같아야 합니다: {len(arr_a)} != {len(arr_b)}"
        )


def _validate_min_observations(arr_a: np.ndarray) -> None:
    """WHY: n < 2 이면 분산 자체가 정의되지 않는다."""
    if len(arr_a) < _MIN_OBSERVATIONS:
        raise ValueError(
            f"관측 수는 {_MIN_OBSERVATIONS} 이상이어야 합니다: {len(arr_a)!r}"
        )
