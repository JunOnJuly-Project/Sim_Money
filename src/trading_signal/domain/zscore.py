"""
ZScore 값 객체 — 스프레드의 표준화 점수.

WHY: float 를 그대로 전달하면 함수 시그니처에서 의미가 불분명해진다.
     래퍼 값 객체로 선언해 'z-score 로 표현된 스프레드 이탈 정도' 라는
     도메인 의미를 타입으로 표현하고, 타입 검사기가 오남용을 잡을 수 있게 한다.
     진입·청산 조건 모두 음·양 z-score 를 허용하므로 범위 불변식은 두지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZScore:
    """스프레드 z-score 값 객체."""

    value: float
