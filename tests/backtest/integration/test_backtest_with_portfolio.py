"""
backtest + portfolio 통합 테스트.

WHY: PortfolioPositionSizer(EqualWeightStrategy) 를 InMemoryBacktestEngine 에
     주입했을 때 RunBacktest 유스케이스 전체 파이프라인이 올바르게 작동하는지
     end-to-end 로 검증한다. portfolio 제약 조건이 실제 수량 계산에 반영되는지
     수기값과 대조한다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from portfolio.adapters.outbound.equal_weight_strategy import EqualWeightStrategy
from portfolio.domain.constraints import PortfolioConstraints

from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine
from backtest.adapters.outbound.in_memory_trade_executor import InMemoryTradeExecutor
from backtest.adapters.outbound.portfolio_position_sizer import PortfolioPositionSizer
from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.price_bar import PriceBar
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


def _engine_with_portfolio(cash_buffer: str = "0") -> InMemoryBacktestEngine:
    """PortfolioPositionSizer 를 주입한 엔진 생성 헬퍼."""
    sizer = PortfolioPositionSizer(
        strategy=EqualWeightStrategy(),
        constraints=PortfolioConstraints(
            cash_buffer=Decimal(cash_buffer),
        ),
    )
    return InMemoryBacktestEngine(trade_executor=InMemoryTradeExecutor(sizer=sizer))


# ---------------------------------------------------------------------------
# 통합 테스트
# ---------------------------------------------------------------------------

class TestBacktestWithPortfolioSizer:
    """PortfolioPositionSizer 주입 end-to-end 검증."""

    def test_cash_buffer_0_일때_기존과_동일한_qty(self) -> None:
        """cash_buffer=0 → EqualWeight 단일 신호 weight=1.0 → 기존 동작과 동일.

        WHY: portfolio 사이저를 주입해도 cash_buffer=0 이면
             StrengthPositionSizer(strength=1.0) 결과와 동일해야
             기본 동작 보장을 확인할 수 있다.
             qty = 10000 / 100 = 100, pnl = (110-100)*100 = 1000
        """
        engine = _engine_with_portfolio(cash_buffer="0")
        t1, t2 = _utc(2024, 1, 1), _utc(2024, 1, 2)
        config = BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t2, ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "AAPL": [_bar("AAPL", "100", t1), _bar("AAPL", "110", t2)],
        }

        result = engine.run(signals=signals, price_history=price_history, config=config)

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.quantity == Decimal("100")
        assert trade.pnl == Decimal("1000")

    def test_cash_buffer_0_2_일때_qty_감소(self) -> None:
        """cash_buffer=0.2 → weight=0.8 → qty=80, pnl=800.

        WHY: cash_buffer 를 적용하면 투자 가능 비율이 낮아져
             수량이 줄고 손익도 비례 감소하는지 확인한다.
             qty = 10000 * 0.8 / 100 = 80
             pnl = (110 - 100) * 80 = 800
        """
        engine = _engine_with_portfolio(cash_buffer="0.2")
        t1, t2 = _utc(2024, 2, 1), _utc(2024, 2, 2)
        config = BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )
        signals = [
            Signal(timestamp=t1, ticker="AAPL", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t2, ticker="AAPL", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "AAPL": [_bar("AAPL", "100", t1), _bar("AAPL", "110", t2)],
        }

        result = engine.run(signals=signals, price_history=price_history, config=config)

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.quantity == Decimal("80")
        assert trade.pnl == Decimal("800")

    def test_비제로_비용_케이스_슬리피지_수수료_cash_buffer_복합(self) -> None:
        """slippage_bps=5, fee_rate=0.001, cash_buffer=0.2 조합 회귀 검증.

        WHY: 비용 파라미터가 모두 0 인 이상적 케이스 외에
             실전에 가까운 비용 구조에서도 pnl 이 올바르게 계산되는지 확인한다.
             슬리피지와 수수료가 적용될 때 pnl 은 반드시 0 이 아닌 음수 방향이다.

        수기 검증:
            slippage_bps=5 → fill_long = 100 * 1.0005 = 100.05
            cash_buffer=0.2 → weight = 0.8 → qty = 10000 * 0.8 / 100.05 ≈ 79.96
            fill_exit = 100 * (1 - 0.0005) = 99.95
            gross_pnl = (99.95 - 100.05) * qty = -0.1 * qty
            entry_fee = 100.05 * qty * 0.001
            exit_fee  = 99.95  * qty * 0.001
            net_pnl < 0 (슬리피지+수수료 모두 손실 방향)
        """
        engine = _engine_with_portfolio(cash_buffer="0.2")
        t1, t2 = _utc(2024, 4, 1), _utc(2024, 4, 2)
        config = BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("5"),
        )
        signals = [
            Signal(timestamp=t1, ticker="COST", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t2, ticker="COST", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "COST": [_bar("COST", "100", t1), _bar("COST", "100", t2)],
        }

        result = engine.run(signals=signals, price_history=price_history, config=config)

        assert len(result.trades) == 1
        trade = result.trades[0]
        # 슬리피지+수수료 존재 → 동가 청산에도 순손실이어야 한다
        assert trade.pnl < Decimal("0"), f"비용 적용 후 pnl 은 음수여야 함, 실제: {trade.pnl}"

    def test_기본_엔진과_portfolio_엔진이_strength1_cash_buffer0_동일결과(self) -> None:
        """StrengthPositionSizer(기본) vs PortfolioPositionSizer(buffer=0) → 동일 결과.

        WHY: portfolio 사이저 도입이 기존 동작을 깨지 않음을 양쪽 비교로 보장한다.
        """
        default_engine = InMemoryBacktestEngine()
        portfolio_engine = _engine_with_portfolio(cash_buffer="0")

        t1, t2 = _utc(2024, 3, 1), _utc(2024, 3, 2)
        config = BacktestConfig(
            initial_capital=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )
        signals = [
            Signal(timestamp=t1, ticker="TSLA", side=Side.LONG, strength=Decimal("1.0")),
            Signal(timestamp=t2, ticker="TSLA", side=Side.EXIT, strength=Decimal("1.0")),
        ]
        price_history = {
            "TSLA": [_bar("TSLA", "200", t1), _bar("TSLA", "220", t2)],
        }

        result_default = default_engine.run(signals=signals, price_history=price_history, config=config)
        result_portfolio = portfolio_engine.run(signals=signals, price_history=price_history, config=config)

        assert result_default.trades[0].quantity == result_portfolio.trades[0].quantity
        assert result_default.trades[0].pnl == result_portfolio.trades[0].pnl
