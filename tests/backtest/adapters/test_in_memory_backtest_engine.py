"""
InMemoryBacktestEngine 어댑터 기능 테스트 (TDD RED 단계).

WHY: M2 S4 에서는 NotImplementedError 를 제거하고 실제 동작을 구현한다.
     이 테스트는 BacktestEngine Protocol 준수 여부, 기본 조립 가능 여부,
     단순 E2E 1케이스를 RED 로 미리 명세한다.
     구현 전에는 NotImplementedError 혹은 AssertionError 로 RED 상태가 된다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backtest.application.ports.backtest_engine import BacktestEngine
from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.price_bar import PriceBar
from backtest.domain.result import BacktestResult
from backtest.domain.signal import Side, Signal


# ---------------------------------------------------------------------------
# 헬퍼
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


def _default_config() -> BacktestConfig:
    """기본 BacktestConfig — fee/slippage 없음."""
    return BacktestConfig(
        initial_capital=Decimal("10000"),
        fee_rate=Decimal("0"),
        slippage_bps=Decimal("0"),
    )


# ---------------------------------------------------------------------------
# 테스트 클래스
# ---------------------------------------------------------------------------

class TestInMemoryBacktestEngine_Protocol_준수:
    """BacktestEngine Protocol isinstance 검사."""

    def test_BacktestEngine_Protocol을_준수한다(self) -> None:
        """WHY: @runtime_checkable Protocol 을 충족해야 포트 기반 DI 가 가능하다.
               isinstance 검사로 구조적 서브타이핑을 런타임에 검증한다."""
        from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine

        engine = InMemoryBacktestEngine()
        assert isinstance(engine, BacktestEngine)

    def test_인자_없이_생성할_수_있다(self) -> None:
        """WHY: DI 컨테이너 없이도 기본 생성이 가능해야 테스트와 스크립트에서 쉽게 사용할 수 있다."""
        from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine

        engine = InMemoryBacktestEngine()
        assert engine is not None


class TestInMemoryBacktestEngine_run_NotImplementedError_제거:
    """M2 S4 에서 NotImplementedError 가 제거된 상태를 기대한다."""

    def test_빈_입력으로_run이_NotImplementedError를_던지지_않는다(self) -> None:
        """WHY: M2 S3 스켈레톤의 NotImplementedError 가 M2 S4 에서 제거되어야 한다.
               빈 입력 기준으로 정상 반환(BacktestResult)을 기대한다."""
        from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine

        engine = InMemoryBacktestEngine()
        config = _default_config()

        # NotImplementedError 없이 정상 반환되어야 한다
        result = engine.run(signals=[], price_history={}, config=config)
        assert isinstance(result, BacktestResult)

    def test_빈_입력이면_trades가_비어있다(self) -> None:
        """WHY: 신호가 없으면 체결이 없으므로 trades 가 빈 tuple 이어야 한다."""
        from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine

        engine = InMemoryBacktestEngine()
        result = engine.run(signals=[], price_history={}, config=_default_config())

        assert result.trades == ()


class TestInMemoryBacktestEngine_E2E_단순:
    """단일 LONG→EXIT 사이클 E2E 검증."""

    def test_LONG_EXIT_사이클이면_BacktestResult를_반환한다(self) -> None:
        """WHY: 엔진의 조립(TradeExecutor + PerformanceCalculator 내장)과
               유스케이스 흐름이 모두 올바를 때만 BacktestResult 를 반환한다.
               가장 단순한 E2E 로 전체 파이프라인을 연기 검증한다."""
        from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine

        engine = InMemoryBacktestEngine()
        t1 = _utc(2024, 1, 1)
        t2 = _utc(2024, 1, 2)

        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t2, ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "AAPL": [
                _bar("AAPL", close="100", ts=t1),
                _bar("AAPL", close="110", ts=t2),
            ]
        }

        result = engine.run(
            signals=signals,
            price_history=price_history,
            config=_default_config(),
        )

        assert isinstance(result, BacktestResult)
        assert len(result.trades) == 1
        assert result.metrics is not None
