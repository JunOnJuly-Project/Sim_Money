"""
SimilarityStrategy 포트 Protocol 호환성 테스트 (TDD RED 단계).

WHY: SimilarityStrategy 는 유사도 계산 어댑터들이 반드시 충족해야 할 계약이다.
     Protocol 멤버 존재 여부를 사전에 검증해 어댑터 계층의 계약 위반을 조기에 탐지한다.
"""
from __future__ import annotations

from similarity.application.ports import SimilarityStrategy


def test_SimilarityStrategy_는_compute_메서드를_가진다():
    """SimilarityStrategy Protocol 이 compute 메서드를 정의하고 있어야 한다.

    WHY: Protocol 멤버 존재 확인은 포트 정의 누락을 구현 이전에 감지하는
         가장 단순하고 빠른 계약 검증 방법이다.
    """
    assert hasattr(SimilarityStrategy, "compute")
