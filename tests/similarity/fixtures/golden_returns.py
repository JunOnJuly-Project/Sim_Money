"""
골든 회귀 테스트용 결정론적 로그수익률 생성기.

WHY: 골든 회귀 테스트(T-REG-01~05) 는 WeightedSumStrategy 의 수치 출력을
     미래 리팩터 후에도 동일하게 보장하는 것이 목적이다.
     numpy seed 를 고정해 결정론적 시계열을 생성하면 어떤 환경·세션에서 실행해도
     동일한 float 값이 나온다.

상수 정의:
    N_STANDARD  = 252  (표준 거래일 수)
    N_SHORT     = 15   (rolling_window=20 보다 짧은 시계열, T-REG-05 용)
    SEED_UNCORR = 42   (무상관 케이스 seed, T-REG-03)
    SEED_WEAK   = 123  (약 양상관 케이스 seed, T-REG-04)
    SEED_SHORT  = 7    (짧은 시계열 케이스 seed, T-REG-05)
"""
from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# 공개 상수 — 테스트 파일이 임포트해서 참조한다
# ---------------------------------------------------------------------------

N_STANDARD: int = 252
N_SHORT: int = 15

SEED_UNCORR: int = 42
SEED_WEAK: int = 123
SEED_SHORT: int = 7


# ---------------------------------------------------------------------------
# 공개 생성 함수
# ---------------------------------------------------------------------------


def make_strongly_positive(n: int = N_STANDARD) -> tuple[list[float], list[float]]:
    """T-REG-01: 완전 양상관 시계열 쌍.

    WHY: a = linspace, b = 2*a + 상수 로 선형 관계를 만들어
         Pearson ρ ≈ 1, shape ≈ 1, stability ≈ 1 을 유도한다.
         seed 가 필요 없는 결정론적 생성이다.

    Returns:
        (a, b) — N 개 요소의 float 리스트 쌍
    """
    a = np.linspace(0.001, 0.010, n)
    b = 2.0 * a + 0.001
    return a.tolist(), b.tolist()


def make_strongly_negative(n: int = N_STANDARD) -> tuple[list[float], list[float]]:
    """T-REG-02: 완전 음상관 시계열 쌍.

    WHY: b = -a 로 완전 역방향 선형 관계를 만들어
         Pearson ρ = -1, shape ≈ 1, stability ≈ 1 을 유도한다.

    Returns:
        (a, b) — N 개 요소의 float 리스트 쌍
    """
    a = np.linspace(0.001, 0.010, n)
    b = -a
    return a.tolist(), b.tolist()


def make_uncorrelated(n: int = N_STANDARD, seed: int = SEED_UNCORR) -> tuple[list[float], list[float]]:
    """T-REG-03: 통계적으로 독립된 무상관 시계열 쌍.

    WHY: 두 시퀀스를 독립 정규 분포에서 개별 샘플링하면
         이론적으로 E[ρ] = 0 이 되어 |score| 가 작아야 한다.
         seed 고정으로 매 실행마다 동일한 '무상관' 쌍을 생성한다.

    Returns:
        (a, b) — N 개 요소의 float 리스트 쌍
    """
    rng = np.random.default_rng(seed=seed)
    a = rng.standard_normal(n)
    b = rng.standard_normal(n)
    return a.tolist(), b.tolist()


def make_weakly_positive(n: int = N_STANDARD, seed: int = SEED_WEAK) -> tuple[list[float], list[float]]:
    """T-REG-04: 약한 양상관 시계열 쌍.

    WHY: b = a + 0.5 * noise 구조로 신호(a) 와 노이즈가 혼재하는
         실제 금융 시계열의 전형적인 약 양상관 상황을 재현한다.

    Returns:
        (a, b) — N 개 요소의 float 리스트 쌍
    """
    rng = np.random.default_rng(seed=seed)
    a = rng.standard_normal(n)
    noise = rng.standard_normal(n)
    b = a + 0.5 * noise
    return a.tolist(), b.tolist()


def make_short_series(n: int = N_SHORT, seed: int = SEED_SHORT) -> tuple[list[float], list[float]]:
    """T-REG-05: rolling_window(20) 보다 짧은 시계열 쌍.

    WHY: N=15 < window=20 이면 _stability 내부에서 _rolling_pearson_std 가
         None 을 반환해 stability = 0 이 된다.
         이 케이스는 stability 항이 0 으로 처리되는 경계 조건을 고정한다.

    Returns:
        (a, b) — N 개 요소의 float 리스트 쌍
    """
    rng = np.random.default_rng(seed=seed)
    a = rng.standard_normal(n)
    b = rng.standard_normal(n)
    return a.tolist(), b.tolist()
