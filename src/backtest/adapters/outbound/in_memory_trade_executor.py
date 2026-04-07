"""
인메모리 TradeExecutor 어댑터.

WHY: 테스트·백테스트 시뮬레이션에서 외부 브로커 API 없이도
     슬리피지·수수료 공식을 정확히 재현하기 위해 인메모리로 구현한다.
     실거래 어댑터로 교체 시 이 파일만 바꾸면 되도록 포트 계약을 준수한다.
"""
from __future__ import annotations

from decimal import Decimal

from backtest.adapters.outbound.strength_position_sizer import StrengthPositionSizer
from backtest.application.ports.position_sizer import PositionSizer
from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.position import Position
from backtest.domain.price_bar import PriceBar
from backtest.domain.signal import Signal
from backtest.domain.trade import Trade

# 슬리피지 계산 기준 단위 (1bps = 0.01%)
_BPS_DIVISOR = Decimal("10000")


class InMemoryTradeExecutor:
    """슬리피지·수수료 공식을 메모리 내에서 시뮬레이션하는 TradeExecutor 어댑터."""

    def __init__(self, sizer: PositionSizer | None = None) -> None:
        """PositionSizer 를 주입받아 초기화한다.

        WHY: 사이징 전략을 생성자 주입으로 분리해 Portfolio 기반 사이저 등
             다양한 구현체를 기존 호출부 변경 없이 교체할 수 있다.
             기본값 StrengthPositionSizer 로 기존 동작과 100% 호환된다.
        """
        self._sizer: PositionSizer = sizer if sizer is not None else StrengthPositionSizer()

    def open_long(
        self,
        signal: Signal,
        bar: PriceBar,
        config: BacktestConfig,
        available_cash: Decimal,
    ) -> Position:
        """LONG 포지션을 생성한다.

        WHY: 진입 시 슬리피지는 불리한 방향(가격 상승)으로 적용해야
             실제 시장과 동일한 비용 구조를 재현할 수 있다.
        """
        fill_price = _calc_long_fill(bar.close, config.slippage_bps)
        weight = self._sizer.size(signal, available_cash)
        quantity = _calc_quantity(available_cash, weight, fill_price)
        return Position(
            ticker=signal.ticker,
            quantity=quantity,
            entry_price=fill_price,
            entry_time=bar.timestamp,
        )

    def close_position(
        self,
        position: Position,
        bar: PriceBar,
        config: BacktestConfig,
    ) -> Trade:
        """포지션을 청산하고 완결 Trade 를 반환한다.

        WHY: 청산 시 슬리피지는 불리한 방향(가격 하락)으로 적용해야
             실제 매도 비용을 정확히 반영할 수 있다.
        """
        exit_fill = _calc_exit_fill(bar.close, config.slippage_bps)
        pnl = _calc_pnl(
            position.entry_price,
            exit_fill,
            position.quantity,
            config.fee_rate,
        )
        return Trade(
            ticker=position.ticker,
            entry_time=position.entry_time,
            exit_time=bar.timestamp,
            entry_price=position.entry_price,
            exit_price=exit_fill,
            quantity=position.quantity,
            pnl=pnl,
        )


# ---------------------------------------------------------------------------
# 내부 순수 함수 — 단일 책임, 테스트 가능
# ---------------------------------------------------------------------------

def _calc_long_fill(close: Decimal, slippage_bps: Decimal) -> Decimal:
    """LONG 진입 체결가: close * (1 + slippage_bps / 10000)."""
    return close * (Decimal("1") + slippage_bps / _BPS_DIVISOR)


def _calc_exit_fill(close: Decimal, slippage_bps: Decimal) -> Decimal:
    """EXIT 청산 체결가: close * (1 - slippage_bps / 10000)."""
    return close * (Decimal("1") - slippage_bps / _BPS_DIVISOR)


def _calc_quantity(available_cash: Decimal, weight: Decimal, fill_price: Decimal) -> Decimal:
    """투자 수량: (available_cash * weight) / fill_price.

    WHY: 매개변수명을 'strength' 에서 'weight' 로 변경해
         PositionSizer.size() 반환값이 '비중(weight)' 임을 명확히 한다.
         strength 는 신호 강도이고, 사이저가 반환하는 것은 투자 비중이다.
    """
    return (available_cash * weight) / fill_price


def _calc_pnl(
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: Decimal,
    fee_rate: Decimal,
) -> Decimal:
    """pnl = (exit - entry) * qty - entry_fee - exit_fee.

    WHY: 진입·청산 양쪽 수수료를 모두 차감해야 실제 순손익을 정확히 산출한다.
    """
    entry_fee = entry_price * quantity * fee_rate
    exit_fee = exit_price * quantity * fee_rate
    return (exit_price - entry_price) * quantity - entry_fee - exit_fee
