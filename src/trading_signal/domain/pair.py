"""
Pair 값 객체 — 페어 트레이딩의 두 종목 쌍.

WHY: (A, B) 와 (B, A) 를 동일 페어로 취급해야 유사도 조회·캐시 중복을 막을 수 있다.
     __post_init__ 에서 문자열 비교로 a < b 정규화를 강제하면
     호출부에서 순서를 신경 쓰지 않아도 항상 동일한 키가 생성된다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pair:
    """두 종목으로 구성된 페어 트레이딩 대상 쌍.

    Attributes:
        a: 알파벳 순서상 앞에 오는 종목 코드
        b: 알파벳 순서상 뒤에 오는 종목 코드
    """

    a: str
    b: str

    def __post_init__(self) -> None:
        """페어 불변식 검증 및 정규화."""
        if not self.a or not self.b:
            raise ValueError("종목 코드는 빈 문자열일 수 없습니다.")
        if self.a == self.b:
            raise ValueError(f"자기 자신과 페어를 구성할 수 없습니다: {self.a!r}")
        # WHY: frozen dataclass 에서 직접 대입 불가 → object.__setattr__ 우회
        if self.a > self.b:
            original_a = self.a
            object.__setattr__(self, "a", self.b)
            object.__setattr__(self, "b", original_a)
