"""
backtest 도메인 값 객체 단위 테스트 (TDD RED 단계).

WHY: backtest L3 도메인의 핵심 불변식을 구현 전에 테스트로 명세화한다.
     frozen dataclass 기반 값 객체는 불변성·타입 안전성·경계값을 모두
     생성 시점에 검증해야 실거래 파이프라인에서 잘못된 상태가 전파되지 않는다.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal

import pytest

# WHY: 아직 미구현 상태이므로 import 자체가 RED 의 시작점이다.
from backtest.domain.price_bar import PriceBar
from backtest.domain.signal import Side, Signal
from backtest.domain.position import Position
from backtest.domain.trade import Trade
from backtest.domain.metrics import PerformanceMetrics
from backtest.domain.result import BacktestResult


# ─────────────────────────────────────────────
# 공통 픽스처
# ─────────────────────────────────────────────
_NOW = datetime(2024, 1, 2, 9, 0, 0, tzinfo=timezone.utc)
_LATER = datetime(2024, 1, 3, 9, 0, 0, tzinfo=timezone.utc)


# ═════════════════════════════════════════════
# PriceBar
# ═════════════════════════════════════════════
class TestPriceBar_정상:
    def test_유효한_가격으로_PriceBar를_생성한다(self):
        """WHY: 정상 OHLCV 값으로 객체 생성이 성공해야 한다."""
        bar = PriceBar(
            timestamp=_NOW,
            ticker="005930",
            open=Decimal("70000"),
            high=Decimal("72000"),
            low=Decimal("69000"),
            close=Decimal("71000"),
            volume=Decimal("1000000"),
        )
        assert bar.ticker == "005930"
        assert bar.high == Decimal("72000")

    def test_high_equal_low_는_허용된다(self):
        """WHY: 갭 없는 봉(시가=고가=저가=종가)은 유효한 거래 상태다."""
        bar = PriceBar(
            timestamp=_NOW,
            ticker="AAPL",
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=Decimal("0"),
        )
        assert bar.high == bar.low


class TestPriceBar_불변식_위반:
    def test_high_보다_low가_크면_ValueError를_던진다(self):
        """WHY: 고가 < 저가는 OHLCV 데이터 손상을 의미한다."""
        with pytest.raises(ValueError, match="high.*low|low.*high"):
            PriceBar(
                timestamp=_NOW,
                ticker="005930",
                open=Decimal("70000"),
                high=Decimal("68000"),  # high < low → 위반
                low=Decimal("69000"),
                close=Decimal("70000"),
                volume=Decimal("500000"),
            )

    def test_close가_high를_초과하면_ValueError를_던진다(self):
        """WHY: 종가가 고가를 넘는 것은 물리적으로 불가능하다."""
        with pytest.raises(ValueError):
            PriceBar(
                timestamp=_NOW,
                ticker="005930",
                open=Decimal("70000"),
                high=Decimal("71000"),
                low=Decimal("69000"),
                close=Decimal("72000"),  # close > high → 위반
                volume=Decimal("500000"),
            )

    def test_volume이_음수이면_ValueError를_던진다(self):
        """WHY: 거래량은 물리적으로 음수가 불가능하다."""
        with pytest.raises(ValueError, match="volume"):
            PriceBar(
                timestamp=_NOW,
                ticker="005930",
                open=Decimal("70000"),
                high=Decimal("72000"),
                low=Decimal("69000"),
                close=Decimal("71000"),
                volume=Decimal("-1"),
            )

    def test_ticker가_빈_문자열이면_ValueError를_던진다(self):
        """WHY: 빈 ticker 는 종목 식별이 불가능한 오염 데이터다."""
        with pytest.raises(ValueError, match="ticker"):
            PriceBar(
                timestamp=_NOW,
                ticker="",
                open=Decimal("70000"),
                high=Decimal("72000"),
                low=Decimal("69000"),
                close=Decimal("71000"),
                volume=Decimal("500000"),
            )

    def test_PriceBar는_frozen이라_필드_변경_시_FrozenInstanceError를_던진다(self):
        """WHY: 가격 이력은 사실(fact)이므로 불변 보장이 필수다."""
        bar = PriceBar(
            timestamp=_NOW,
            ticker="005930",
            open=Decimal("70000"),
            high=Decimal("72000"),
            low=Decimal("69000"),
            close=Decimal("71000"),
            volume=Decimal("500000"),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            bar.close = Decimal("99999")  # type: ignore[misc]


# ═════════════════════════════════════════════
# Signal / Side
# ═════════════════════════════════════════════
class TestSide_Enum:
    def test_LONG_SHORT_EXIT_멤버가_존재한다(self):
        """WHY: 매수·매도·청산 세 방향이 신호의 전체 집합이다."""
        assert Side.LONG
        assert Side.SHORT
        assert Side.EXIT


class TestSignal_정상:
    def test_유효한_strength로_Signal을_생성한다(self):
        """WHY: strength=Decimal("0.8") 처럼 [0,1] 범위 내의 값이면 정상 생성되어야 한다."""
        sig = Signal(
            timestamp=_NOW,
            ticker="005930",
            side=Side.LONG,
            strength=Decimal("0.8"),
        )
        assert sig.strength == Decimal("0.8")
        assert sig.side is Side.LONG

    def test_strength가_경계값_0_과_1에서_Signal을_생성한다(self):
        """WHY: 경계값 0 과 1 은 유효한 강도 값이다."""
        sig_min = Signal(timestamp=_NOW, ticker="A", side=Side.EXIT, strength=Decimal("0"))
        sig_max = Signal(timestamp=_NOW, ticker="A", side=Side.LONG, strength=Decimal("1"))
        assert sig_min.strength == Decimal("0")
        assert sig_max.strength == Decimal("1")


class TestSignal_불변식_위반:
    def test_strength가_0_미만이면_ValueError를_던진다(self):
        """WHY: 음수 신호 강도는 의미 없으며 하위 계산에서 오류를 유발한다."""
        with pytest.raises(ValueError, match="strength"):
            Signal(timestamp=_NOW, ticker="005930", side=Side.LONG, strength=Decimal("-0.1"))

    def test_strength가_1_초과이면_ValueError를_던진다(self):
        """WHY: 정규화된 강도는 최대 1.0 이어야 한다."""
        with pytest.raises(ValueError, match="strength"):
            Signal(timestamp=_NOW, ticker="005930", side=Side.SHORT, strength=Decimal("1.01"))

    def test_Signal은_frozen이라_필드_변경_시_FrozenInstanceError를_던진다(self):
        """WHY: 신호는 생성 후 변경되면 재현성이 깨진다."""
        sig = Signal(timestamp=_NOW, ticker="A", side=Side.LONG, strength=Decimal("0.5"))
        with pytest.raises(dataclasses.FrozenInstanceError):
            sig.strength = Decimal("0.9")  # type: ignore[misc]


# ═════════════════════════════════════════════
# Position
# ═════════════════════════════════════════════
class TestPosition_정상:
    def test_유효한_수량과_가격으로_Position을_생성한다(self):
        """WHY: 1주 이상의 양수 수량과 양수 진입가는 정상 포지션이다."""
        pos = Position(
            ticker="005930",
            quantity=Decimal("10"),
            entry_price=Decimal("70000"),
            entry_time=_NOW,
        )
        assert pos.quantity == Decimal("10")
        assert pos.entry_price == Decimal("70000")


class TestPosition_불변식_위반:
    def test_quantity가_0이면_ValueError를_던진다(self):
        """WHY: 0주 포지션은 실질적으로 포지션이 없는 상태다."""
        with pytest.raises(ValueError, match="quantity"):
            Position(
                ticker="005930",
                quantity=Decimal("0"),
                entry_price=Decimal("70000"),
                entry_time=_NOW,
            )

    def test_entry_price가_0_이하이면_ValueError를_던진다(self):
        """WHY: 가격은 항상 양수여야 한다. 0 또는 음수 가격은 데이터 오류다."""
        with pytest.raises(ValueError, match="entry_price"):
            Position(
                ticker="005930",
                quantity=Decimal("10"),
                entry_price=Decimal("0"),
                entry_time=_NOW,
            )

    def test_Position은_frozen이라_필드_변경_시_FrozenInstanceError를_던진다(self):
        """WHY: 포지션 진입 정보는 사후 변경되어서는 안 된다."""
        pos = Position(
            ticker="005930",
            quantity=Decimal("10"),
            entry_price=Decimal("70000"),
            entry_time=_NOW,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            pos.quantity = Decimal("999")  # type: ignore[misc]


# ═════════════════════════════════════════════
# Trade
# ═════════════════════════════════════════════
class TestTrade_정상:
    def test_유효한_매매_정보로_Trade를_생성한다(self):
        """WHY: 진입 < 청산, 양수 수량, 양수 가격이면 완결된 거래다."""
        trade = Trade(
            ticker="005930",
            entry_time=_NOW,
            exit_time=_LATER,
            entry_price=Decimal("70000"),
            exit_price=Decimal("72000"),
            quantity=Decimal("10"),
            pnl=Decimal("20000"),
        )
        assert trade.pnl == Decimal("20000")

    def test_exit_time이_entry_time과_같아도_허용된다(self):
        """WHY: 당일 진입·청산(당일 매매)은 정상적인 거래 유형이다."""
        trade = Trade(
            ticker="A",
            entry_time=_NOW,
            exit_time=_NOW,
            entry_price=Decimal("100"),
            exit_price=Decimal("101"),
            quantity=Decimal("1"),
            pnl=Decimal("1"),
        )
        assert trade.entry_time == trade.exit_time


class TestTrade_불변식_위반:
    def test_exit_time이_entry_time보다_이전이면_ValueError를_던진다(self):
        """WHY: 청산 시각이 진입 시각보다 앞서는 것은 시간 역전 오류다."""
        with pytest.raises(ValueError, match="exit_time|entry_time"):
            Trade(
                ticker="005930",
                entry_time=_LATER,
                exit_time=_NOW,  # exit < entry → 위반
                entry_price=Decimal("70000"),
                exit_price=Decimal("72000"),
                quantity=Decimal("10"),
                pnl=Decimal("20000"),
            )

    def test_quantity가_0이하이면_ValueError를_던진다(self):
        """WHY: 거래 수량은 최소 1주 이상이어야 한다."""
        with pytest.raises(ValueError, match="quantity"):
            Trade(
                ticker="005930",
                entry_time=_NOW,
                exit_time=_LATER,
                entry_price=Decimal("70000"),
                exit_price=Decimal("72000"),
                quantity=Decimal("0"),
                pnl=Decimal("0"),
            )

    def test_Trade는_frozen이라_필드_변경_시_FrozenInstanceError를_던진다(self):
        """WHY: 완결된 거래는 수정되어서는 안 된다 — 감사 추적 요건."""
        trade = Trade(
            ticker="A",
            entry_time=_NOW,
            exit_time=_LATER,
            entry_price=Decimal("100"),
            exit_price=Decimal("110"),
            quantity=Decimal("5"),
            pnl=Decimal("50"),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            trade.pnl = Decimal("9999")  # type: ignore[misc]


# ═════════════════════════════════════════════
# PerformanceMetrics
# ═════════════════════════════════════════════
class TestPerformanceMetrics_정상:
    def test_유효한_지표로_PerformanceMetrics를_생성한다(self):
        """WHY: 양의 수익률, 정상 샤프, 음의 최대낙폭, 유효 승률이면 정상이다."""
        metrics = PerformanceMetrics(
            total_return=Decimal("0.15"),
            sharpe=1.5,
            max_drawdown=Decimal("-0.10"),
            win_rate=0.6,
        )
        assert metrics.win_rate == 0.6

    def test_win_rate_경계값_0과_1_모두_허용된다(self):
        """WHY: 전패(0.0) 또는 전승(1.0)도 유효한 백테스트 결과다."""
        m0 = PerformanceMetrics(
            total_return=Decimal("-0.5"),
            sharpe=-2.0,
            max_drawdown=Decimal("-0.5"),
            win_rate=0.0,
        )
        m1 = PerformanceMetrics(
            total_return=Decimal("1.0"),
            sharpe=5.0,
            max_drawdown=Decimal("0"),
            win_rate=1.0,
        )
        assert m0.win_rate == 0.0
        assert m1.win_rate == 1.0


class TestPerformanceMetrics_불변식_위반:
    def test_win_rate가_0_미만이면_ValueError를_던진다(self):
        """WHY: 승률은 확률값이므로 [0, 1] 범위를 벗어날 수 없다."""
        with pytest.raises(ValueError, match="win_rate"):
            PerformanceMetrics(
                total_return=Decimal("0.1"),
                sharpe=1.0,
                max_drawdown=Decimal("-0.05"),
                win_rate=-0.01,
            )

    def test_win_rate가_1_초과이면_ValueError를_던진다(self):
        """WHY: 승률 > 1 은 데이터 오류 또는 계산 버그를 나타낸다."""
        with pytest.raises(ValueError, match="win_rate"):
            PerformanceMetrics(
                total_return=Decimal("0.1"),
                sharpe=1.0,
                max_drawdown=Decimal("-0.05"),
                win_rate=1.001,
            )

    def test_max_drawdown이_양수이면_ValueError를_던진다(self):
        """WHY: 최대낙폭은 손실을 나타내므로 항상 0 이하여야 한다."""
        with pytest.raises(ValueError, match="max_drawdown"):
            PerformanceMetrics(
                total_return=Decimal("0.1"),
                sharpe=1.0,
                max_drawdown=Decimal("0.01"),  # 양수 → 위반
                win_rate=0.5,
            )

    def test_PerformanceMetrics는_frozen이라_필드_변경_시_FrozenInstanceError를_던진다(self):
        """WHY: 성과 지표는 집계 후 고정되어야 재현성이 보장된다."""
        metrics = PerformanceMetrics(
            total_return=Decimal("0.1"),
            sharpe=1.2,
            max_drawdown=Decimal("-0.05"),
            win_rate=0.55,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            metrics.sharpe = 99.9  # type: ignore[misc]


# ═════════════════════════════════════════════
# BacktestResult
# ═════════════════════════════════════════════
class TestBacktestResult_정상:
    def _make_trade(self) -> Trade:
        return Trade(
            ticker="005930",
            entry_time=_NOW,
            exit_time=_LATER,
            entry_price=Decimal("70000"),
            exit_price=Decimal("71000"),
            quantity=Decimal("1"),
            pnl=Decimal("1000"),
        )

    def _make_metrics(self) -> PerformanceMetrics:
        return PerformanceMetrics(
            total_return=Decimal("0.014"),
            sharpe=0.8,
            max_drawdown=Decimal("-0.02"),
            win_rate=1.0,
        )

    def test_trades와_equity_curve가_tuple로_저장된다(self):
        """WHY: BacktestResult 는 불변 결과물이므로 컬렉션도 tuple 이어야 한다."""
        trade = self._make_trade()
        metrics = self._make_metrics()
        result = BacktestResult(
            trades=(trade,),
            equity_curve=(Decimal("1000000"), Decimal("1001000")),
            metrics=metrics,
        )
        assert isinstance(result.trades, tuple)
        assert isinstance(result.equity_curve, tuple)

    def test_빈_trades와_equity_curve도_허용된다(self):
        """WHY: 신호가 하나도 발생하지 않은 백테스트는 유효한 결과다."""
        metrics = self._make_metrics()
        result = BacktestResult(
            trades=(),
            equity_curve=(),
            metrics=metrics,
        )
        assert result.trades == ()

    def test_BacktestResult는_frozen이라_필드_변경_시_FrozenInstanceError를_던진다(self):
        """WHY: 백테스트 결과는 생성 후 절대 변경되어서는 안 된다."""
        metrics = self._make_metrics()
        result = BacktestResult(
            trades=(),
            equity_curve=(),
            metrics=metrics,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.trades = (self._make_trade(),)  # type: ignore[misc]
