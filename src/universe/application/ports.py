"""
Universe 애플리케이션 포트 정의.

WHY: 포트(Port)는 도메인과 외부 어댑터 사이의 계약이다.
     Protocol 로 정의하면 어댑터가 상속 없이 구조적 서브타이핑으로
     계약을 충족할 수 있어 결합도를 낮춘다.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol

from universe.domain.universe_snapshot import UniverseSnapshot


class UniverseSource(Protocol):
    """외부 유니버스 데이터 소스와의 경계를 정의하는 포트.

    WHY: 실제 데이터 소스(KRX API, CSV, DB 등)가 교체되어도
         도메인 로직이 영향을 받지 않도록 인터페이스로 격리한다.
    """

    def fetch(self, name: str, as_of: date) -> UniverseSnapshot:
        """이름과 날짜 기준으로 유니버스 스냅샷을 조회한다.

        Args:
            name: 유니버스 식별 이름 (예: 'KOSPI200').
            as_of: 스냅샷 기준 날짜.

        Returns:
            해당 날짜 기준의 UniverseSnapshot.
        """
        ...
