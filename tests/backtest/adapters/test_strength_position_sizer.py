"""
StrengthPositionSizer 어댑터 단위 테스트.

WHY: signal.strength 를 그대로 비율로 반환하는 기본 동작을 검증한다.
     available_cash 는 이 구현에서 사용되지 않음도 확인한다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backtest.adapters.outbound.strength_position_sizer import StrengthPositionSizer
from backtest.application.ports.position_sizer import PositionSizer
from backtest.domain.signal import Side, Signal


def _signal(strength: str) -> Signal:
    """테스트용 Signal 생성 헬퍼."""
    return Signal(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ticker="AAPL",
        side=Side.LONG,
        strength=Decimal(strength),
    )


class TestStrengthPositionSizer:
    """StrengthPositionSizer 단위 테스트."""

    def test_PositionSizer_프로토콜_준수(self) -> None:
        """PositionSizer 프로토콜을 충족하는지 확인한다."""
        sizer = StrengthPositionSizer()
        assert isinstance(sizer, PositionSizer)

    def test_strength_1_반환(self) -> None:
        """strength=1.0 일 때 1.0 을 반환한다."""
        sizer = StrengthPositionSizer()
        result = sizer.size(_signal("1.0"), Decimal("10000"))
        assert result == Decimal("1.0")

    def test_strength_0_반환(self) -> None:
        """strength=0.0 일 때 0.0 을 반환한다."""
        sizer = StrengthPositionSizer()
        result = sizer.size(_signal("0.0"), Decimal("10000"))
        assert result == Decimal("0.0")

    def test_strength_0_5_반환(self) -> None:
        """strength=0.5 일 때 0.5 를 반환한다."""
        sizer = StrengthPositionSizer()
        result = sizer.size(_signal("0.5"), Decimal("5000"))
        assert result == Decimal("0.5")

    def test_available_cash_무관(self) -> None:
        """available_cash 값과 무관하게 strength 만 반환한다."""
        sizer = StrengthPositionSizer()
        result_small = sizer.size(_signal("0.7"), Decimal("100"))
        result_large = sizer.size(_signal("0.7"), Decimal("9999999"))
        assert result_small == result_large == Decimal("0.7")
