"""
UniverseSource 포트 Protocol 호환성 테스트 (TDD RED 단계).

WHY: UniverseSource 는 외부 데이터 소스와의 경계를 정의하는 포트다.
     실제 구현 클래스가 Protocol 을 올바르게 충족하는지 구조적으로 검증해
     어댑터 계층에서 계약 위반을 조기에 잡아낸다.
"""
from __future__ import annotations

from universe.application.ports import UniverseSource


def test_UniverseSource_는_fetch_메서드를_가진다():
    """UniverseSource Protocol 이 fetch 메서드를 정의하고 있어야 한다.

    WHY: Protocol 멤버 존재 여부를 확인함으로써, 포트 정의 누락을
         구현 이전에 감지한다.
    """
    assert hasattr(UniverseSource, "fetch")
