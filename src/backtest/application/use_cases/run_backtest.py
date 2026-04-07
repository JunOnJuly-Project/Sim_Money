"""
RunBacktest 유스케이스.

WHY: 백테스트 실행 흐름(신호 소비 → 거래 실행 → 성과 계산)을 하나의 유스케이스로
     캡슐화하고, 포트 인터페이스에만 의존해 어댑터 구현을 런타임에 교체 가능하게 한다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from itertools import groupby
from typing import Mapping, Sequence

from backtest.application.ports.performance_calculator import PerformanceCalculator
from backtest.application.ports.trade_executor import TradeExecutor
from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.position import Position
from backtest.domain.price_bar import PriceBar
from backtest.domain.result import BacktestResult
from backtest.domain.signal import Side, Signal
from backtest.domain.trade import Trade


class RunBacktest:
    """백테스트 실행 유스케이스."""

    def __init__(
        self,
        trade_executor: TradeExecutor,
        performance_calculator: PerformanceCalculator,
    ) -> None:
        """포트 구현체를 주입받아 유스케이스를 초기화한다."""
        self._trade_executor = trade_executor
        self._performance_calculator = performance_calculator

    def execute(
        self,
        signals: Sequence[Signal],
        price_history: Mapping[str, Sequence[PriceBar]],
        config: BacktestConfig,
    ) -> BacktestResult:
        """신호·가격 이력·설정을 받아 백테스트를 실행하고 결과를 반환한다."""
        bar_index = _build_bar_index(price_history)
        sorted_signals = sorted(signals, key=lambda s: s.timestamp)

        open_positions: dict[str, Position] = {}
        trades: list[Trade] = []
        available_cash: Decimal = config.initial_capital

        # WHY: 초기 자산을 첫 스냅샷으로 기록해 total_return 계산의 기준점을 확보한다.
        #      이후 매 bar 완료 시 mark-to-market 스냅샷이 추가된다.
        equity_curve: list[tuple[datetime, Decimal]] = []

        if not sorted_signals:
            first_ts = datetime.now(tz=timezone.utc)
            equity_curve.append((first_ts, config.initial_capital))
        else:
            # WHY: 첫 신호 timestamp 이전 초기 자산을 기준점으로 기록한다.
            equity_curve.append((sorted_signals[0].timestamp, config.initial_capital))

        # WHY: timestamp 기준으로 그룹핑해 동시 신호를 일괄 처리한다.
        #      같은 시각의 LONG 신호 여러 개가 현금을 균등 배분받도록 보장한다.
        for ts, group in groupby(sorted_signals, key=lambda s: s.timestamp):
            ts_signals = list(group)
            available_cash = _process_timestamp_signals(
                ts, ts_signals, bar_index, config, available_cash,
                open_positions, trades, self._trade_executor,
            )
            # WHY: 매 bar 처리 완료 후 mark-to-market 스냅샷을 기록한다.
            #      M2 한정: 미실현 손익 = 현재 bar close 기준 mark-to-market.
            snapshot = _calc_equity_snapshot(ts, available_cash, open_positions, bar_index)
            equity_curve.append(snapshot)

        metrics = self._performance_calculator.compute(trades, equity_curve)
        return BacktestResult(
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            metrics=metrics,
        )


# ---------------------------------------------------------------------------
# 내부 함수 — 단일 책임 분리
# ---------------------------------------------------------------------------

def _build_bar_index(
    price_history: Mapping[str, Sequence[PriceBar]],
) -> dict[tuple[str, datetime], PriceBar]:
    """price_history 를 (ticker, timestamp) → PriceBar 딕셔너리로 변환한다.

    WHY: 신호마다 O(1) 조회를 보장해 시뮬레이션 전체 복잡도를 낮춘다.
    """
    index: dict[tuple[str, datetime], PriceBar] = {}
    for ticker, bars in price_history.items():
        for bar in sorted(bars, key=lambda b: b.timestamp):
            index[(ticker, bar.timestamp)] = bar
    return index


def _calc_equity_snapshot(
    ts: datetime,
    available_cash: Decimal,
    open_positions: dict[str, Position],
    bar_index: dict[tuple[str, datetime], PriceBar],
) -> tuple[datetime, Decimal]:
    """현재 timestamp 의 자산 스냅샷을 계산한다.

    M2 한정: 미실현 손익 = 현재 bar close 기준 mark-to-market.
    해당 timestamp 의 bar 가 없는 포지션은 entry_price 로 근사한다.
    정식 구현(히스토리컬 close lookup 등)은 M3 예정.
    """
    unrealized: Decimal = sum(
        (
            bar_index[(pos.ticker, ts)].close * pos.quantity
            if (pos.ticker, ts) in bar_index
            else pos.entry_price * pos.quantity
        )
        for pos in open_positions.values()
    ) or Decimal("0")
    return (ts, available_cash + unrealized)


def _process_timestamp_signals(
    ts: datetime,
    signals: Sequence[Signal],
    bar_index: dict,
    config: BacktestConfig,
    available_cash: Decimal,
    open_positions: dict[str, Position],
    trades: list[Trade],
    executor: TradeExecutor,
) -> Decimal:
    """단일 timestamp 의 신호 목록을 처리하고 갱신된 가용 현금을 반환한다.

    WHY: 같은 timestamp 의 LONG 신호가 여러 개일 때 가용 현금을 균등 분배해야
         각 포지션이 독립적으로 진입할 수 있다.
    """
    long_signals = [s for s in signals if s.side == Side.LONG]
    exit_signals = [s for s in signals if s.side == Side.EXIT]

    # WHY: EXIT 먼저 처리해 현금을 회수한 뒤 LONG 진입에 활용할 수 있게 한다.
    for signal in exit_signals:
        bar = bar_index.get((signal.ticker, signal.timestamp))
        if bar is None:
            continue
        available_cash = _process_exit(
            signal, bar, config, available_cash,
            open_positions, trades, executor,
        )

    # 진입 가능한 LONG 신호만 필터링.
    # WHY: 같은 timestamp 에 동일 ticker LONG 이 2개 이상 오면 두 번째부터 무시한다.
    #      seen 세트로 그룹 내 첫 번째만 허용해 포지션 중복 진입을 방지한다.
    seen: set[str] = set()
    new_long_signals: list[Signal] = []
    for s in long_signals:
        if s.ticker in open_positions or s.ticker in seen:
            continue
        if bar_index.get((s.ticker, s.timestamp)) is None:
            continue
        seen.add(s.ticker)
        new_long_signals.append(s)

    if not new_long_signals:
        return available_cash

    # WHY: 동시 LONG 진입 수로 현금을 균등 분배해 각 포지션이 진입 가능하게 한다.
    cash_per_signal = available_cash / Decimal(str(len(new_long_signals)))

    for signal in new_long_signals:
        bar = bar_index[(signal.ticker, signal.timestamp)]
        position = executor.open_long(signal, bar, config, cash_per_signal)
        open_positions[signal.ticker] = position
        invested = position.entry_price * position.quantity
        available_cash -= invested

    return available_cash


def _process_exit(
    signal: Signal,
    bar: PriceBar,
    config: BacktestConfig,
    available_cash: Decimal,
    open_positions: dict[str, Position],
    trades: list[Trade],
    executor: TradeExecutor,
) -> Decimal:
    """EXIT 신호를 처리하고 갱신된 가용 현금을 반환한다."""
    position = open_positions.pop(signal.ticker, None)
    if position is None:
        return available_cash

    trade = executor.close_position(position, bar, config)
    trades.append(trade)

    # WHY: pnl = (exit - entry) * qty - entry_fee - exit_fee 이므로
    #      available_cash = 투자금 회수 + 순손익으로 복원된다.
    invested = position.entry_price * position.quantity
    return available_cash + invested + trade.pnl
