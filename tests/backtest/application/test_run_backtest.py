"""
RunBacktest 유스케이스 단위 테스트 (TDD RED 단계).

WHY: 포트 인터페이스를 Fake 로 대체해 유스케이스 로직만 격리 검증한다.
     어댑터 구현 완성 전에도 유스케이스 정책(LONG→EXIT 사이클, SHORT 스킵 등)을
     명세할 수 있어야 한다.
     구현 전에는 NotImplementedError 로 RED 상태가 된다.

핵심 정책:
    - LONG 신호: 해당 timestamp의 bar 가 price_history 에 존재해야 Position 생성
    - EXIT 신호: 보유 중인 해당 ticker Position 이 있어야 Trade 생성
    - SHORT 신호: 현재 스코프 밖 → 무시
    - 중복 LONG: 같은 ticker 이미 오픈이면 두 번째 무시
    - EXIT 없이 종료: 오픈 포지션은 Trade 로 변환하지 않음 (미실현 처리)
    - price_history 정렬 보장: 내부에서 timestamp 기준 정렬 후 처리
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

import pytest

from backtest.application.ports.performance_calculator import PerformanceCalculator
from backtest.application.ports.trade_executor import TradeExecutor
from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.metrics import PerformanceMetrics
from backtest.domain.position import Position
from backtest.domain.price_bar import PriceBar
from backtest.domain.result import BacktestResult
from backtest.domain.signal import Side, Signal
from backtest.domain.trade import Trade


# ---------------------------------------------------------------------------
# Fake 구현체 (테스트 전용)
# ---------------------------------------------------------------------------

def _utc(year: int, month: int, day: int) -> datetime:
    """UTC tz-aware datetime 생성 헬퍼."""
    return datetime(year, month, day, tzinfo=timezone.utc)


def _default_config() -> BacktestConfig:
    """기본 테스트용 BacktestConfig."""
    return BacktestConfig(
        initial_capital=Decimal("10000"),
        fee_rate=Decimal("0"),
        slippage_bps=Decimal("0"),
    )


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


class FakeTradeExecutor:
    """테스트용 TradeExecutor Fake.

    WHY: 실제 체결 로직을 배제하고 유스케이스 정책(어떤 신호에서 open/close 를
         호출하는지)만 검증한다. 단순 고정값을 반환한다.
    """

    def __init__(self) -> None:
        self.open_long_calls: list[tuple] = []
        self.close_position_calls: list[tuple] = []

    def open_long(self, signal: Signal, bar: PriceBar, config: BacktestConfig, available_cash: Decimal) -> Position:
        """LONG 포지션 생성 — 고정 qty=100, entry_price=bar.close."""
        self.open_long_calls.append((signal, bar, config, available_cash))
        return Position(
            ticker=signal.ticker,
            quantity=Decimal("100"),
            entry_price=bar.close,
            entry_time=bar.timestamp,
        )

    def close_position(self, position: Position, bar: PriceBar, config: BacktestConfig) -> Trade:
        """포지션 청산 → 고정 pnl = (exit_close - entry) * qty."""
        self.close_position_calls.append((position, bar, config))
        pnl = (bar.close - position.entry_price) * position.quantity
        return Trade(
            ticker=position.ticker,
            entry_time=position.entry_time,
            exit_time=bar.timestamp,
            entry_price=position.entry_price,
            exit_price=bar.close,
            quantity=position.quantity,
            pnl=pnl,
        )

    # TradeExecutor Protocol 호환 (단일 execute 메서드)
    def execute(self, signal, position):  # pragma: no cover
        """Protocol 호환용. 유스케이스는 open_long/close_position 을 직접 호출한다."""
        ...


class FakePerformanceCalculator:
    """테스트용 PerformanceCalculator Fake.

    WHY: 성과 계산 로직을 배제하고 유스케이스가 calculator.compute 를
         정확히 1회 호출하는지만 검증한다.
    """

    def __init__(self) -> None:
        self.compute_calls: list[tuple] = []

    def compute(self, trades, equity_curve):
        """고정 PerformanceMetrics 반환."""
        self.compute_calls.append((trades, equity_curve))
        return PerformanceMetrics(
            total_return=Decimal("0"),
            sharpe=0.0,
            max_drawdown=Decimal("0"),
            win_rate=0.0,
        )


# ---------------------------------------------------------------------------
# 테스트 클래스
# ---------------------------------------------------------------------------

class TestRunBacktest_빈_입력:
    """빈 signals/price_history → 빈 BacktestResult."""

    def test_빈_입력이면_trades가_비어있다(self) -> None:
        """WHY: 신호가 없으면 거래가 발생하지 않아야 한다.
               빈 trades 로 BacktestResult 가 반환되는지 확인한다."""
        from backtest.application.use_cases.run_backtest import RunBacktest

        executor = FakeTradeExecutor()
        calculator = FakePerformanceCalculator()
        use_case = RunBacktest(executor, calculator)

        result = use_case.execute(
            signals=[],
            price_history={},
            config=_default_config(),
        )

        assert isinstance(result, BacktestResult)
        assert result.trades == ()

    def test_빈_입력이면_performance_calculator가_호출된다(self) -> None:
        """WHY: 빈 결과라도 성과 지표는 항상 계산되어야 한다.
               calculator.compute 가 1회 호출되는지 확인한다."""
        from backtest.application.use_cases.run_backtest import RunBacktest

        executor = FakeTradeExecutor()
        calculator = FakePerformanceCalculator()
        use_case = RunBacktest(executor, calculator)

        use_case.execute(signals=[], price_history={}, config=_default_config())

        assert len(calculator.compute_calls) == 1


class TestRunBacktest_LONG_EXIT_사이클:
    """단일 LONG→EXIT 사이클 정상 처리."""

    def test_LONG_EXIT_사이클이면_Trade_1개가_생성된다(self) -> None:
        """WHY: 기본 사이클인 LONG 진입 후 EXIT 청산이 정확히 1개의 Trade 를 만들어야 한다."""
        from backtest.application.use_cases.run_backtest import RunBacktest

        executor = FakeTradeExecutor()
        calculator = FakePerformanceCalculator()
        use_case = RunBacktest(executor, calculator)

        t1 = _utc(2024, 1, 1)
        t2 = _utc(2024, 1, 2)
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=1.0),
            Signal(timestamp=t2, ticker="AAPL", side=Side.EXIT, strength=1.0),
        ]
        price_history = {
            "AAPL": [
                _bar("AAPL", close="100", ts=t1),
                _bar("AAPL", close="110", ts=t2),
            ]
        }

        result = use_case.execute(
            signals=signals,
            price_history=price_history,
            config=_default_config(),
        )

        assert len(result.trades) == 1

    def test_LONG_EXIT_사이클에서_PerformanceCalculator가_호출된다(self) -> None:
        """WHY: 거래 종료 후 성과 지표 계산이 반드시 실행되어야 한다."""
        from backtest.application.use_cases.run_backtest import RunBacktest

        executor = FakeTradeExecutor()
        calculator = FakePerformanceCalculator()
        use_case = RunBacktest(executor, calculator)

        t1 = _utc(2024, 1, 1)
        t2 = _utc(2024, 1, 2)
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=1.0),
            Signal(timestamp=t2, ticker="AAPL", side=Side.EXIT, strength=1.0),
        ]
        price_history = {
            "AAPL": [
                _bar("AAPL", close="100", ts=t1),
                _bar("AAPL", close="110", ts=t2),
            ]
        }

        use_case.execute(
            signals=signals,
            price_history=price_history,
            config=_default_config(),
        )

        assert len(calculator.compute_calls) == 1


class TestRunBacktest_미체결_신호:
    """신호 timestamp 에 bar 가 없으면 드랍."""

    def test_bar_없는_timestamp의_신호는_무시된다(self) -> None:
        """WHY: 가격 데이터가 없는 시점의 신호는 체결 불가 → Trade 생성 없이 드랍해야 한다."""
        from backtest.application.use_cases.run_backtest import RunBacktest

        executor = FakeTradeExecutor()
        calculator = FakePerformanceCalculator()
        use_case = RunBacktest(executor, calculator)

        t1 = _utc(2024, 1, 1)
        t_missing = _utc(2024, 1, 5)  # price_history 에 없는 날짜

        signals = [
            Signal(timestamp=t_missing, ticker="AAPL", side=Side.LONG, strength=1.0),
        ]
        price_history = {
            "AAPL": [_bar("AAPL", close="100", ts=t1)]  # t_missing 의 bar 없음
        }

        result = use_case.execute(
            signals=signals,
            price_history=price_history,
            config=_default_config(),
        )

        # LONG 신호가 드랍되어 open_long 호출 없음 → trade 없음
        assert result.trades == ()
        assert len(executor.open_long_calls) == 0


class TestRunBacktest_중복_LONG:
    """같은 ticker 에 이미 오픈 포지션이 있을 때 두 번째 LONG 무시."""

    def test_중복_LONG_신호는_첫_번째만_처리된다(self) -> None:
        """WHY: 중복 포지션 진입은 의도치 않은 레버리지 증가를 유발한다.
               같은 ticker 에 오픈 포지션이 있으면 추가 LONG 을 무시해야 한다."""
        from backtest.application.use_cases.run_backtest import RunBacktest

        executor = FakeTradeExecutor()
        calculator = FakePerformanceCalculator()
        use_case = RunBacktest(executor, calculator)

        t1 = _utc(2024, 1, 1)
        t2 = _utc(2024, 1, 2)
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=1.0),
            Signal(timestamp=t2, ticker="AAPL", side=Side.LONG, strength=1.0),  # 중복
        ]
        price_history = {
            "AAPL": [
                _bar("AAPL", close="100", ts=t1),
                _bar("AAPL", close="105", ts=t2),
            ]
        }

        use_case.execute(
            signals=signals,
            price_history=price_history,
            config=_default_config(),
        )

        # open_long 은 단 1회만 호출되어야 한다
        assert len(executor.open_long_calls) == 1

    def test_동일_timestamp_동일_ticker_LONG_2개는_1개만_반영된다(self) -> None:
        """WHY: 동일 timestamp 그룹 내에서 같은 ticker LONG 이 2개 들어오면
               두 번째는 포지션을 덮어쓰거나 중복 진입해서는 안 된다.
               seen 세트 로직이 그룹 내 첫 번째만 허용함을 회귀 테스트로 고정한다."""
        from backtest.application.use_cases.run_backtest import RunBacktest

        executor = FakeTradeExecutor()
        calculator = FakePerformanceCalculator()
        use_case = RunBacktest(executor, calculator)

        t1 = _utc(2024, 1, 1)
        # 동일 timestamp + 동일 ticker LONG 신호 2개
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=1.0),
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=0.5),
        ]
        price_history = {
            "AAPL": [_bar("AAPL", close="100", ts=t1)]
        }

        result = use_case.execute(
            signals=signals,
            price_history=price_history,
            config=_default_config(),
        )

        # open_long 은 단 1회만 호출되어야 한다 (두 번째 LONG 은 seen 세트에서 드랍)
        assert len(executor.open_long_calls) == 1
        # trades 는 EXIT 없이 종료되었으므로 0건
        assert result.trades == ()


class TestRunBacktest_EXIT_없이_종료:
    """EXIT 없이 종료 → 오픈 포지션은 Trade 로 변환하지 않음."""

    def test_EXIT_없이_종료된_포지션은_trades에_포함되지_않는다(self) -> None:
        """WHY: EXIT 신호 없이 종료된 포지션은 미실현 손익이므로
               확정 Trade 목록에 포함하지 않는 정책을 준수한다."""
        from backtest.application.use_cases.run_backtest import RunBacktest

        executor = FakeTradeExecutor()
        calculator = FakePerformanceCalculator()
        use_case = RunBacktest(executor, calculator)

        t1 = _utc(2024, 1, 1)
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=1.0),
            # EXIT 신호 없음
        ]
        price_history = {
            "AAPL": [_bar("AAPL", close="100", ts=t1)]
        }

        result = use_case.execute(
            signals=signals,
            price_history=price_history,
            config=_default_config(),
        )

        assert result.trades == ()


class TestRunBacktest_SHORT_스킵:
    """SHORT 신호는 현재 스코프 밖 → 무시."""

    def test_SHORT_신호는_무시된다(self) -> None:
        """WHY: M1 스코프에서 SHORT 는 구현하지 않는다.
               SHORT 신호가 와도 포지션·거래를 생성하지 않아야 한다."""
        from backtest.application.use_cases.run_backtest import RunBacktest

        executor = FakeTradeExecutor()
        calculator = FakePerformanceCalculator()
        use_case = RunBacktest(executor, calculator)

        t1 = _utc(2024, 1, 1)
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.SHORT, strength=1.0),
        ]
        price_history = {
            "AAPL": [_bar("AAPL", close="100", ts=t1)]
        }

        result = use_case.execute(
            signals=signals,
            price_history=price_history,
            config=_default_config(),
        )

        assert result.trades == ()
        assert len(executor.open_long_calls) == 0


class TestRunBacktest_price_history_정렬:
    """정렬되지 않은 price_history 입력 → 내부 정렬 후 처리."""

    def test_비정렬_price_history도_정상_처리된다(self) -> None:
        """WHY: 외부에서 순서 보장 없이 bar 를 넘길 수 있다.
               유스케이스가 timestamp 기준으로 내부 정렬하면 체결 순서가 올바르다."""
        from backtest.application.use_cases.run_backtest import RunBacktest

        executor = FakeTradeExecutor()
        calculator = FakePerformanceCalculator()
        use_case = RunBacktest(executor, calculator)

        t1 = _utc(2024, 1, 1)
        t2 = _utc(2024, 1, 2)
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=1.0),
            Signal(timestamp=t2, ticker="AAPL", side=Side.EXIT, strength=1.0),
        ]
        # 의도적으로 역순 제공
        price_history = {
            "AAPL": [
                _bar("AAPL", close="110", ts=t2),  # 역순
                _bar("AAPL", close="100", ts=t1),
            ]
        }

        result = use_case.execute(
            signals=signals,
            price_history=price_history,
            config=_default_config(),
        )

        # 정렬 후 처리되어 Trade 1개 생성
        assert len(result.trades) == 1
