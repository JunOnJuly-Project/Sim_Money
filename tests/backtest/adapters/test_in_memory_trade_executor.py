"""
InMemoryTradeExecutor 어댑터 단위 테스트 (TDD RED 단계).

WHY: TradeExecutor 포트의 구체 구현인 InMemoryTradeExecutor 가
     슬리피지·수수료·수량 계산 공식을 정확히 준수하는지 검증한다.
     구현 전에는 ModuleNotFoundError 로 RED 상태가 된다.

체결가 공식:
    LONG  fill_price = close * (1 + slippage_bps / 10_000)
    EXIT  fill_price = close * (1 - slippage_bps / 10_000)

수량 공식:
    quantity = (available_cash * Decimal(str(strength))) / fill_price

손익 공식:
    pnl = (exit_price - entry_price) * quantity - entry_fee - exit_fee
    fee = notional * fee_rate  (진입/청산 각각)
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.price_bar import PriceBar
from backtest.domain.signal import Side, Signal


# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------

def _utc(year: int, month: int, day: int) -> datetime:
    """UTC tz-aware datetime 생성 헬퍼."""
    return datetime(year, month, day, tzinfo=timezone.utc)


def _bar(ticker: str, close: str, ts: datetime) -> PriceBar:
    """테스트용 PriceBar 생성 헬퍼."""
    c = Decimal(close)
    return PriceBar(
        timestamp=ts,
        ticker=ticker,
        open=c,
        high=c,
        low=c,
        close=c,
        volume=Decimal("1000"),
    )


def _config(fee_rate: str = "0", slippage_bps: str = "0") -> BacktestConfig:
    """테스트용 BacktestConfig 생성 헬퍼."""
    return BacktestConfig(
        initial_capital=Decimal("10000"),
        fee_rate=Decimal(fee_rate),
        slippage_bps=Decimal(slippage_bps),
    )


def _long_signal(ticker: str, strength: Decimal = Decimal("1"), ts: datetime | None = None) -> Signal:
    """테스트용 LONG 신호 생성 헬퍼."""
    return Signal(
        timestamp=ts or _utc(2024, 1, 1),
        ticker=ticker,
        side=Side.LONG,
        strength=strength,
    )


def _exit_signal(ticker: str, ts: datetime | None = None) -> Signal:
    """테스트용 EXIT 신호 생성 헬퍼."""
    return Signal(
        timestamp=ts or _utc(2024, 1, 2),
        ticker=ticker,
        side=Side.EXIT,
        strength=Decimal("1"),
    )


# ---------------------------------------------------------------------------
# 테스트 클래스
# ---------------------------------------------------------------------------

class TestInMemoryTradeExecutor_임포트:
    """어댑터 모듈 임포트 가능 여부 검증."""

    def test_어댑터를_임포트할_수_있다(self) -> None:
        """WHY: 파일이 없거나 문법 오류가 있으면 CI 전체가 실패한다.
               import 성공 여부로 존재 및 문법을 조기에 감지한다."""
        from backtest.adapters.outbound.in_memory_trade_executor import (  # noqa: F401
            InMemoryTradeExecutor,
        )

    def test_인스턴스를_생성할_수_있다(self) -> None:
        """WHY: 생성자가 필수 인자를 요구하지 않아야 쉽게 조립할 수 있다."""
        from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor
        executor = InMemoryTradeExecutor()
        assert executor is not None


class TestInMemoryTradeExecutor_open_long_기본:
    """open_long — fee=0, slippage=0 기본 케이스."""

    def test_LONG_진입_시_수량과_진입가가_정확하다(self) -> None:
        """WHY: fee=0, slippage=0 조건에서 수량 = available_cash / close 여야 한다.
               가장 단순한 케이스를 먼저 통과시켜 공식 기반을 검증한다."""
        from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor

        executor = InMemoryTradeExecutor()
        signal = _long_signal("AAPL", strength=Decimal("1"))
        bar = _bar("AAPL", close="100", ts=_utc(2024, 1, 1))
        config = _config(fee_rate="0", slippage_bps="0")
        available_cash = Decimal("10000")

        position = executor.open_long(signal, bar, config, available_cash)

        # 수량 = 10000 / 100 = 100
        assert position.quantity == Decimal("100")
        # 진입가 = close (슬리피지 없음)
        assert position.entry_price == Decimal("100")
        assert position.ticker == "AAPL"

    def test_LONG_진입_시_entry_time이_bar_timestamp와_일치한다(self) -> None:
        """WHY: 체결 시각은 신호가 아닌 봉의 timestamp 이어야 재현성이 보장된다."""
        from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor

        executor = InMemoryTradeExecutor()
        ts = _utc(2024, 3, 15)
        signal = _long_signal("AAPL", ts=ts)
        bar = _bar("AAPL", close="50", ts=ts)
        config = _config()
        available_cash = Decimal("5000")

        position = executor.open_long(signal, bar, config, available_cash)

        assert position.entry_time == ts


class TestInMemoryTradeExecutor_close_position_기본:
    """close_position — fee=0, slippage=0 기본 케이스."""

    def test_EXIT_시_pnl이_가격_차이_곱하기_수량이다(self) -> None:
        """WHY: fee=0, slippage=0 조건에서 pnl = (exit - entry) * qty 여야 한다."""
        from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor
        from backtest.domain.position import Position

        executor = InMemoryTradeExecutor()
        entry_ts = _utc(2024, 1, 1)
        exit_ts = _utc(2024, 1, 2)

        # 진입: 100원, 수량 100개
        position = Position(
            ticker="AAPL",
            quantity=Decimal("100"),
            entry_price=Decimal("100"),
            entry_time=entry_ts,
        )
        bar = _bar("AAPL", close="110", ts=exit_ts)
        config = _config(fee_rate="0", slippage_bps="0")

        trade = executor.close_position(position, bar, config)

        # pnl = (110 - 100) * 100 = 1000
        assert trade.pnl == Decimal("1000")
        assert trade.ticker == "AAPL"
        assert trade.entry_price == Decimal("100")
        assert trade.exit_price == Decimal("110")
        assert trade.quantity == Decimal("100")

    def test_EXIT_시_exit_time이_entry_time_이상이다(self) -> None:
        """WHY: Trade 불변식 — exit_time >= entry_time 을 어댑터가 깨뜨리면 안 된다."""
        from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor
        from backtest.domain.position import Position

        executor = InMemoryTradeExecutor()
        entry_ts = _utc(2024, 1, 1)
        exit_ts = _utc(2024, 1, 2)

        position = Position(
            ticker="AAPL",
            quantity=Decimal("100"),
            entry_price=Decimal("100"),
            entry_time=entry_ts,
        )
        bar = _bar("AAPL", close="105", ts=exit_ts)
        config = _config()

        trade = executor.close_position(position, bar, config)

        assert trade.exit_time >= trade.entry_time


class TestInMemoryTradeExecutor_수수료:
    """fee_rate 반영 케이스."""

    def test_fee_rate_0001_반영_후_pnl이_감소한다(self) -> None:
        """WHY: 진입/청산 양쪽 수수료가 pnl 에서 차감되어야 실제 수익을 정확히 반영한다.
               entry_fee = entry_price * qty * fee_rate
               exit_fee  = exit_price  * qty * fee_rate
               pnl = (exit - entry) * qty - entry_fee - exit_fee"""
        from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor
        from backtest.domain.position import Position

        executor = InMemoryTradeExecutor()
        entry_ts = _utc(2024, 1, 1)
        exit_ts = _utc(2024, 1, 2)
        config = _config(fee_rate="0.001", slippage_bps="0")

        # 진입가 100, 수량 계산: available_cash=10000, strength=Decimal("1.0")
        # fill_price(LONG)=100, qty=10000/100=100
        signal = _long_signal("AAPL", strength=Decimal("1"))
        bar_entry = _bar("AAPL", close="100", ts=entry_ts)
        position = executor.open_long(signal, bar_entry, config, Decimal("10000"))

        bar_exit = _bar("AAPL", close="110", ts=exit_ts)
        trade = executor.close_position(position, bar_exit, config)

        # 수기 계산:
        # qty = 10000 / 100 = 100
        # entry_fee = 100 * 100 * 0.001 = 10
        # exit_fee  = 110 * 100 * 0.001 = 11
        # pnl = (110 - 100) * 100 - 10 - 11 = 1000 - 21 = 979
        assert trade.pnl == Decimal("979")


class TestInMemoryTradeExecutor_슬리피지:
    """slippage_bps 반영 케이스."""

    def test_slippage_10bps_LONG_진입가가_close보다_높다(self) -> None:
        """WHY: LONG 진입 시 슬리피지는 불리한 방향(높은 가격)으로 적용된다.
               fill_price = close * (1 + 10 / 10_000) = close * 1.001"""
        from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor

        executor = InMemoryTradeExecutor()
        config = _config(fee_rate="0", slippage_bps="10")
        signal = _long_signal("AAPL", strength=Decimal("1"))
        bar = _bar("AAPL", close="100", ts=_utc(2024, 1, 1))

        position = executor.open_long(signal, bar, config, Decimal("10000"))

        # fill_price = 100 * 1.001 = 100.1
        expected_fill = Decimal("100") * (1 + Decimal("10") / Decimal("10000"))
        assert position.entry_price == expected_fill

    def test_slippage_10bps_EXIT_청산가가_close보다_낮다(self) -> None:
        """WHY: EXIT 시 슬리피지는 불리한 방향(낮은 가격)으로 적용된다.
               fill_price = close * (1 - 10 / 10_000) = close * 0.999"""
        from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor
        from backtest.domain.position import Position

        executor = InMemoryTradeExecutor()
        config = _config(fee_rate="0", slippage_bps="10")
        entry_ts = _utc(2024, 1, 1)
        exit_ts = _utc(2024, 1, 2)

        position = Position(
            ticker="AAPL",
            quantity=Decimal("100"),
            entry_price=Decimal("100"),
            entry_time=entry_ts,
        )
        bar = _bar("AAPL", close="110", ts=exit_ts)

        trade = executor.close_position(position, bar, config)

        # fill_price = 110 * 0.999 = 109.89
        expected_exit = Decimal("110") * (1 - Decimal("10") / Decimal("10000"))
        assert trade.exit_price == expected_exit


class TestInMemoryTradeExecutor_strength:
    """strength 에 따른 수량 비례 케이스."""

    def test_strength_05이면_수량이_1의_절반이다(self) -> None:
        """WHY: strength=Decimal("0.5") 는 가용 현금의 절반만 투자하라는 신호다.
               quantity = (available_cash * 0.5) / fill_price"""
        from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor

        executor = InMemoryTradeExecutor()
        config = _config(fee_rate="0", slippage_bps="0")

        signal_full = _long_signal("AAPL", strength=Decimal("1"))
        signal_half = _long_signal("AAPL", strength=Decimal("0.5"))
        bar = _bar("AAPL", close="100", ts=_utc(2024, 1, 1))
        available_cash = Decimal("10000")

        pos_full = executor.open_long(signal_full, bar, config, available_cash)
        pos_half = executor.open_long(signal_half, bar, config, available_cash)

        # strength=Decimal("1.0") → qty=100, strength=Decimal("0.5") → qty=50
        assert pos_half.quantity == pos_full.quantity / 2


class TestInMemoryTradeExecutor_Decimal_정밀도:
    """Decimal 연산 정밀도 유지 검증."""

    def test_소수점_수량이_Decimal_타입으로_반환된다(self) -> None:
        """WHY: float 연산은 0.1 + 0.2 != 0.3 같은 오차가 발생한다.
               금융 계산에서 Decimal 을 유지해야 누적 오차를 방지한다."""
        from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor

        executor = InMemoryTradeExecutor()
        # close=3 이면 qty = 10000 / 3 → 소수 발생
        config = _config(fee_rate="0", slippage_bps="0")
        signal = _long_signal("AAPL", strength=Decimal("1"))
        bar = _bar("AAPL", close="3", ts=_utc(2024, 1, 1))

        position = executor.open_long(signal, bar, config, Decimal("10000"))

        assert isinstance(position.quantity, Decimal)
        assert isinstance(position.entry_price, Decimal)

    def test_pnl이_Decimal_타입으로_반환된다(self) -> None:
        """WHY: pnl 도 Decimal 이어야 성과 집계 시 float 오차가 누적되지 않는다."""
        from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor
        from backtest.domain.position import Position

        executor = InMemoryTradeExecutor()
        config = _config(fee_rate="0.001", slippage_bps="5")
        entry_ts = _utc(2024, 1, 1)
        exit_ts = _utc(2024, 1, 2)

        position = Position(
            ticker="AAPL",
            quantity=Decimal("33.3333"),
            entry_price=Decimal("100"),
            entry_time=entry_ts,
        )
        bar = _bar("AAPL", close="110", ts=exit_ts)

        trade = executor.close_position(position, bar, config)

        assert isinstance(trade.pnl, Decimal)
