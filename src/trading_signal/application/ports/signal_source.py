"""
SignalSource 포트 인터페이스.

WHY: 신호 생성 전략을 교체 가능하게 하려면 포트 추상화가 필요하다.
     @runtime_checkable Protocol 로 선언해 isinstance 검사를 지원하면서도
     명시적 상속 없이 구조적 서브타이핑(Duck Typing)을 유지한다.
     Mapping/Sequence 타입을 사용해 도메인이 특정 컨테이너 구현에 의존하지 않는다.
"""
from __future__ import annotations

from typing import Mapping, Protocol, Sequence, runtime_checkable

from trading_signal.domain.trading_signal import TradingSignal


@runtime_checkable
class SignalSource(Protocol):
    """매매 신호 생성기 포트.

    구현체는 price_map 에서 종목별 가격 시계열을 읽어
    TradingSignal 목록을 반환해야 한다.
    """

    def generate(
        self,
        price_map: Mapping[str, Sequence[float]],
    ) -> list[TradingSignal]:
        """가격 맵에서 매매 신호 목록을 생성한다.

        Args:
            price_map: 종목코드 → 종가 시계열 매핑

        Returns:
            생성된 TradingSignal 목록 (없으면 빈 리스트)
        """
        ...
