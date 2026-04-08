"""
RunBacktest 유스케이스.

WHY: 백테스트 실행 흐름(신호 소비 → 거래 실행 → 성과 계산)을 하나의 유스케이스로
     캡슐화하고, 포트 인터페이스에만 의존해 어댑터 구현을 런타임에 교체 가능하게 한다.

sizer 분리 이유:
     기존에는 InMemoryTradeExecutor 가 내부에서 PositionSizer 를 호출했다.
     이 구조에서는 동일 타임스탬프 신호 전체를 한 번에 전달하는 size_group 이 불가능하다.
     유스케이스가 sizer 를 직접 보유하고 그룹 단위로 호출한 뒤 weight 를 executor 에 전달한다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from itertools import groupby
from typing import Mapping, Sequence

from backtest.application.ports.performance_calculator import PerformanceCalculator
from backtest.application.ports.position_sizer import PositionSizer
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
        sizer: PositionSizer | None = None,
    ) -> None:
        """포트 구현체를 주입받아 유스케이스를 초기화한다.

        WHY: sizer 를 유스케이스가 직접 보유해 size_group 으로
             동일 타임스탬프 신호를 일괄 처리할 수 있게 한다.
             sizer=None 이면 조립자(InMemoryBacktestEngine)가 기본값을 주입한다.
             유스케이스는 어댑터(StrengthPositionSizer)를 직접 import 하지 않아
             헥사고날 레이어 계약(application → adapters 금지)을 준수한다.
        """
        self._trade_executor = trade_executor
        self._performance_calculator = performance_calculator
        # WHY: 기본 사이저는 strength/N 로 기존 동작을 유지한다. 어댑터를 import 하지
        #      않기 위해 application 내부에 순수 클래스로 정의한다.
        self._sizer: PositionSizer = sizer if sizer is not None else _DefaultStrengthSizer()

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
        #      sizer.size_group 으로 그룹 전체를 한 번에 처리해
        #      포트폴리오 제약(cash_buffer, max_position_weight)이 형제 신호를 인지한다.
        for ts, group in groupby(sorted_signals, key=lambda s: s.timestamp):
            ts_signals = list(group)
            available_cash = _process_timestamp_signals(
                ts, ts_signals, bar_index, config, available_cash,
                open_positions, trades, self._trade_executor, self._sizer,
            )
            # WHY: 매 bar 처리 완료 후 mark-to-market 스냅샷을 기록한다.
            #      M2 한정: 미실현 손익 = 현재 bar close 기준 mark-to-market.
            snapshot = _calc_equity_snapshot(ts, available_cash, open_positions, bar_index)
            equity_curve.append(snapshot)

        # WHY: 동일 timestamp 가 연속으로 기록되면 _validate_intervals 에서
        #      간격=0 으로 비등간격 오류가 발생한다. 중복 timestamp 는 최신 값만 유지한다.
        equity_curve = _dedup_equity_curve(equity_curve)

        metrics = self._performance_calculator.compute(trades, equity_curve)
        return BacktestResult(
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            metrics=metrics,
        )


# ---------------------------------------------------------------------------
# 내부 함수 — 단일 책임 분리
# ---------------------------------------------------------------------------

def _dedup_equity_curve(
    equity_curve: list[tuple[datetime, Decimal]],
) -> list[tuple[datetime, Decimal]]:
    """동일 timestamp 중복 포인트를 제거하고 최신 값만 유지한다.

    WHY: equity_curve 에 초기 자본 기준점과 첫 bar 스냅샷이 같은 timestamp 로
         삽입될 수 있다. 중복 timestamp 는 등간격 검증을 오탐하게 만들므로
         최신(후행) 포인트를 남기고 이전 포인트는 제거한다.
    """
    seen: dict[datetime, Decimal] = {}
    for ts, val in equity_curve:
        seen[ts] = val  # 동일 timestamp 면 나중 값으로 덮어쓴다
    return [(ts, val) for ts, val in seen.items()]


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
    sizer: PositionSizer,
) -> Decimal:
    """단일 timestamp 의 신호 목록을 처리하고 갱신된 가용 현금을 반환한다.

    WHY: sizer.size_group 으로 형제 신호 전체를 한 번에 처리해
         포트폴리오 제약(cash_buffer, max_position_weight)이 올바르게 적용된다.
         기존 cash_per_signal 균등 분배 방식을 제거하고 사이저에 위임한다.
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

    # WHY: 그룹 진입 시점의 총자본을 스냅샷으로 고정한다.
    #      weight = '그룹 진입 시점 총자본 대비 비율' 의미가 되어
    #      각 open_long 이 동일한 기준 현금으로 수량을 계산한다.
    #      available_cash 자체는 각 체결 후 차감해 다음 그룹에 정확히 넘긴다.
    initial_cash_for_group = available_cash
    weights = sizer.size_group(new_long_signals, initial_cash_for_group)

    for signal, weight in zip(new_long_signals, weights):
        bar = bar_index[(signal.ticker, signal.timestamp)]
        position = executor.open_long(signal, bar, config, initial_cash_for_group, weight)
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


class _DefaultStrengthSizer:
    """기본 PositionSizer — 그룹 내 각 신호에 strength/N 가중치를 부여한다.

    WHY: application 레이어가 어댑터(StrengthPositionSizer)를 import 하지 않도록
         동등한 로직을 내부에 순수 클래스로 복제한다. 기존 엔진 동작
         (cash_per_signal = available_cash/N × strength) 과 수학적으로 동일하다.
    """

    def size(self, signal: Signal, available_cash: Decimal) -> Decimal:  # noqa: ARG002
        return signal.strength

    def size_group(
        self, signals: Sequence[Signal], available_cash: Decimal  # noqa: ARG002
    ) -> Sequence[Decimal]:
        if not signals:
            return []
        n = Decimal(len(signals))
        return [s.strength / n for s in signals]
