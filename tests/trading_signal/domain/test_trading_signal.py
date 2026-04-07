"""
TradingSignal 값 객체 단위 테스트.

WHY: strength [0,1] 불변식과 frozen 불변성을 검증해
     하위 컴포넌트가 비정상 강도로 오동작하는 시나리오를 사전 차단한다.
"""
from datetime import datetime
from decimal import Decimal

import pytest

from trading_signal.domain.side import Side
from trading_signal.domain.trading_signal import TradingSignal

_NOW = datetime(2024, 1, 1, 9, 0, 0)


class TestTradingSignalCreation:
    """정상 생성 케이스."""

    def test_LONG_신호_정상_생성(self):
        sig = TradingSignal(_NOW, "AAPL", Side.LONG, Decimal("0.8"))
        assert sig.ticker == "AAPL"
        assert sig.side == Side.LONG
        assert sig.strength == Decimal("0.8")

    def test_SHORT_신호_정상_생성(self):
        sig = TradingSignal(_NOW, "MSFT", Side.SHORT, Decimal("0.5"))
        assert sig.side == Side.SHORT

    def test_EXIT_신호_정상_생성(self):
        sig = TradingSignal(_NOW, "AAPL", Side.EXIT, Decimal("1"))
        assert sig.side == Side.EXIT

    def test_strength_경계값_0_허용(self):
        sig = TradingSignal(_NOW, "AAPL", Side.LONG, Decimal("0"))
        assert sig.strength == Decimal("0")

    def test_strength_경계값_1_허용(self):
        sig = TradingSignal(_NOW, "AAPL", Side.LONG, Decimal("1"))
        assert sig.strength == Decimal("1")


class TestTradingSignalInvariants:
    """불변식 위반 시 ValueError 검증."""

    def test_strength_음수_에러(self):
        with pytest.raises(ValueError, match="0.0 이상"):
            TradingSignal(_NOW, "AAPL", Side.LONG, Decimal("-0.1"))

    def test_strength_1_초과_에러(self):
        with pytest.raises(ValueError, match="1.0 이하"):
            TradingSignal(_NOW, "AAPL", Side.LONG, Decimal("1.1"))

    def test_ticker_빈_문자열_에러(self):
        with pytest.raises(ValueError, match="ticker"):
            TradingSignal(_NOW, "", Side.LONG, Decimal("0.5"))

    def test_frozen_객체는_필드_변경_불가(self):
        sig = TradingSignal(_NOW, "AAPL", Side.LONG, Decimal("0.5"))
        with pytest.raises(Exception):
            sig.ticker = "GOOG"  # type: ignore[misc]

    def test_동일_필드_신호는_동등하다(self):
        sig1 = TradingSignal(_NOW, "AAPL", Side.LONG, Decimal("0.5"))
        sig2 = TradingSignal(_NOW, "AAPL", Side.LONG, Decimal("0.5"))
        assert sig1 == sig2
