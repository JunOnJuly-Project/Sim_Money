"""
Spearman 순위 상관계수 기반 유사도 전략.

WHY: ADR-002 의 SimilarityStrategy 포트는 전략 교체 가능성을 전제한다.
     SpearmanStrategy 는 WeightedSumStrategy 와 동일한 compute(a, b) -> float
     인터페이스를 제공해, 비선형 단조 관계 탐지가 필요한 경우 무중단 교체를 가능케 한다.
     Pearson ρ 가 놓치는 비선형 단조 패턴(y = exp(x) 등)이 실거래 신호에서
     빈번하게 나타나므로 Phase 2 전략으로 도입한다.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from similarity.domain.spearman import spearman_correlation


@dataclass(frozen=True)
class SpearmanStrategy:
    """Spearman 순위 상관계수 기반 유사도 전략.

    WHY: frozen dataclass 로 불변성을 보장해 공유 인스턴스에서도 사이드 이펙트가 없다.
         상태를 가지지 않으므로 결정론적 순수 함수처럼 동작한다.
    """

    def compute(self, a: Sequence[float], b: Sequence[float]) -> float:
        """두 수치 시퀀스의 Spearman 유사도 점수를 반환한다.

        WHY: spearman_correlation 의 단순 래퍼로, Correlation 값 객체를 float 로
             변환하고 부동소수점 미세 오차를 clip 으로 흡수한다.
             입력 검증은 spearman_correlation 에 위임해 책임을 중앙화한다.

        Args:
            a: 첫 번째 관측값 시퀀스
            b: 두 번째 관측값 시퀀스 (a 와 길이가 같아야 함)

        Returns:
            Spearman ρ ∈ [-1, 1]

        Raises:
            ValueError: 길이 불일치, 관측 수 부족, 표준편차 0 시
        """
        correlation = spearman_correlation(a, b)
        return float(np.clip(correlation.value, -1.0, 1.0))
