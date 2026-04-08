"""
StrengthPositionSizer 기본 구현 어댑터.

WHY: 기존 InMemoryTradeExecutor._calc_quantity 의 동작(signal.strength 를 그대로 비율로 사용)을
     PositionSizer 포트 계약으로 캡슐화한다.
     기본값으로 주입되어 기존 호출부가 변경 없이 동일 결과를 유지한다.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from backtest.domain.signal import Signal


class StrengthPositionSizer:
    """signal.strength 를 투자 비율로 그대로 사용하는 기본 사이저."""

    def size(self, signal: Signal, available_cash: Decimal) -> Decimal:
        """signal.strength 를 투자 비율로 반환한다.

        WHY: strength 는 이미 [0, 1] 범위로 검증된 값이므로
             별도 변환 없이 비율로 직접 사용할 수 있다.
             available_cash 는 이 구현에서 사용하지 않는다(인터페이스 일관성).
        """
        return signal.strength

    def size_group(
        self,
        signals: Sequence[Signal],
        available_cash: Decimal,
    ) -> Sequence[Decimal]:
        """각 신호의 strength 를 N 으로 나눠 weight 를 반환한다.

        WHY: 엔진 루프가 initial_cash_for_group 스냅샷 후 weight 를 곱해
             qty = initial_cash * weight / price 로 계산한다.
             기존 동작은 cash_per_signal * strength / price = (cash/N) * strength / price 였으므로
             동일 결과를 보존하려면 strength / N 으로 정규화해야 한다.
             available_cash 는 이 구현에서 사용하지 않는다(인터페이스 일관성).
        """
        n = len(signals)
        if n == 0:
            return []
        return [s.strength / Decimal(n) for s in signals]
