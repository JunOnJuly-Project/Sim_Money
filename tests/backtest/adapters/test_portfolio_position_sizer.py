"""
PortfolioPositionSizer 어댑터 단위 테스트.

WHY: EqualWeightStrategy 를 주입해 단일 signal → weight 변환이
     portfolio 제약 조건(cash_buffer, max_position_weight)을
     정확히 반영하는지 검증한다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from portfolio.adapters.outbound.equal_weight_strategy import EqualWeightStrategy
from portfolio.domain.constraints import PortfolioConstraints

from backtest.adapters.outbound.portfolio_position_sizer import PortfolioPositionSizer
from backtest.application.ports.position_sizer import PositionSizer
from backtest.domain.signal import Side, Signal


def _signal(ticker: str = "AAPL", strength: str = "1.0") -> Signal:
    """테스트용 Signal 생성 헬퍼."""
    return Signal(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ticker=ticker,
        side=Side.LONG,
        strength=Decimal(strength),
    )


def _sizer(cash_buffer: str = "0", max_position_weight: str = "1") -> PortfolioPositionSizer:
    """테스트용 PortfolioPositionSizer 생성 헬퍼."""
    return PortfolioPositionSizer(
        strategy=EqualWeightStrategy(),
        constraints=PortfolioConstraints(
            cash_buffer=Decimal(cash_buffer),
            max_position_weight=Decimal(max_position_weight),
        ),
    )


class TestPortfolioPositionSizer:
    """PortfolioPositionSizer 단위 테스트."""

    def test_PositionSizer_프로토콜_준수(self) -> None:
        """PositionSizer 프로토콜을 충족하는지 확인한다."""
        sizer = _sizer()
        assert isinstance(sizer, PositionSizer)

    def test_cash_buffer_0_일때_weight_1(self) -> None:
        """cash_buffer=0, 단일 신호 → EqualWeight 결과 1.0."""
        sizer = _sizer(cash_buffer="0")
        result = sizer.size(_signal(), Decimal("10000"))
        assert result == Decimal("1")

    def test_cash_buffer_0_2_일때_weight_0_8(self) -> None:
        """cash_buffer=0.2, 단일 신호 → investable=0.8 → weight 0.8."""
        sizer = _sizer(cash_buffer="0.2")
        result = sizer.size(_signal(), Decimal("10000"))
        assert result == Decimal("0.8")

    def test_max_position_weight_0_5_캡_적용(self) -> None:
        """max_position_weight=0.5, 단일 신호 → 캡 0.5 적용."""
        sizer = _sizer(cash_buffer="0", max_position_weight="0.5")
        result = sizer.size(_signal(), Decimal("10000"))
        assert result == Decimal("0.5")

    def test_available_cash_무관(self) -> None:
        """available_cash 는 이 구현에서 사용되지 않는다."""
        sizer = _sizer(cash_buffer="0.1")
        result_small = sizer.size(_signal(), Decimal("100"))
        result_large = sizer.size(_signal(), Decimal("9999999"))
        assert result_small == result_large
