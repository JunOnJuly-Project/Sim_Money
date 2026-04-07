"""
공적분 기반 유사도 전략.

WHY: ADR-002 의 SimilarityStrategy 포트는 전략 교체 가능성을 전제한다.
     CointegrationStrategy 는 WeightedSumStrategy·SpearmanStrategy 와 동일한
     compute(a, b) -> float 인터페이스를 제공해, 장기 균형 관계 탐지가 필요한
     경우(통계적 차익거래, 페어 트레이딩) 무중단 교체를 가능케 한다.
     score = 1 - p_value 로 공적분이 강할수록 1에 근접한다.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from similarity.domain.cointegration import cointegration_test


@dataclass(frozen=True)
class CointegrationStrategy:
    """Engle-Granger 공적분 검정 기반 유사도 전략.

    WHY: frozen dataclass 로 불변성을 보장해 공유 인스턴스에서도 사이드 이펙트가 없다.
         상태를 가지지 않으므로 결정론적 순수 함수처럼 동작해 백테스트 재현성을 보장한다.
    """

    def compute(self, a: Sequence[float], b: Sequence[float]) -> float:
        """두 수치 시퀀스의 공적분 기반 유사도 점수를 반환한다.

        WHY: score = 1 - p_value 변환으로 공적분이 강할수록(p_value→0) score→1 이 된다.
             clip 으로 부동소수점 미세 오차를 흡수해 [0, 1] 범위를 보장한다.
             입력 검증은 cointegration_test 에 위임해 책임을 중앙화한다.

        Args:
            a: 첫 번째 관측값 시퀀스
            b: 두 번째 관측값 시퀀스 (a 와 길이가 같아야 함)

        Returns:
            공적분 유사도 점수 ∈ [0, 1]

        Raises:
            ValueError: 길이 불일치, 관측 수 부족, 상수 시계열 시
        """
        result = cointegration_test(a, b)
        return float(np.clip(1.0 - result.p_value, 0.0, 1.0))
