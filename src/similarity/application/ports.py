"""
유사도 계산 포트 (Port) 정의.

WHY: SimilarityStrategy 를 Protocol 로 선언하면 어댑터가 명시적 상속 없이
     구조적 서브타이핑으로 계약을 충족할 수 있다(Duck Typing 유지).
     이를 통해 도메인 레이어가 특정 구현에 의존하지 않아 DIP 를 준수한다.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SimilarityStrategy(Protocol):
    """유사도 전략 포트.

    WHY: ADR-002 에 따라 유사도 공식은 반드시 이 포트를 통해서만 호출한다.
         직접 하드코딩을 금지해 공식 교체(Spearman, DTW, DCC-GARCH 등) 시
         호출 코드를 변경하지 않아도 되도록 한다.
    """

    def compute(self, a: list[float], b: list[float]) -> float:
        """두 수치 시퀀스의 유사도 점수를 계산한다.

        Args:
            a: 첫 번째 관측값 시퀀스
            b: 두 번째 관측값 시퀀스

        Returns:
            유사도 점수 (구현체마다 범위 정의 상이)
        """
        ...
