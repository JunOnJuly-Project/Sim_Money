"""
비율 기반 성과 지표 계산기 어댑터.

WHY: 총 수익률·샤프 비율·MDD·승률은 모두 비율(ratio) 지표이므로
     이 어댑터에서 일관된 공식으로 계산한다.
     Decimal → float 변환은 이 경계 내부에서만 발생하도록 제한한다.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Sequence

from backtest.domain.metrics import PerformanceMetrics
from backtest.domain.trade import Trade

# 연 거래일 수 (일별 샤프 → 연율화 기준)
TRADING_DAYS_PER_YEAR = 252

# sqrt(252) 는 일별 샤프를 연율화하는 인수
_ANNUALIZATION_FACTOR = math.sqrt(TRADING_DAYS_PER_YEAR)

_ZERO = Decimal("0")
_ONE = Decimal("1")


class RatioPerformanceCalculator:
    """샤프 비율·MDD·승률·총 수익률을 계산하는 PerformanceCalculator 어댑터.

    WHY: risk_free_rate 를 생성자에서 받아 인스턴스 수준으로 관리하면
         compute() 호출마다 중복 전달 없이 일관된 기준이 유지된다.
         BacktestConfig 에서 읽어 주입하는 확장도 이 설계로 자연스럽게 지원된다.
         (호출부 확장 예시: RatioPerformanceCalculator(config.risk_free_rate))
    """

    def __init__(self, risk_free_rate: float = 0.0) -> None:
        # WHY: 기본값 0.0 으로 기존 호출부(인자 없는 생성자)가 깨지지 않는다.
        self.risk_free_rate = risk_free_rate

    def compute(
        self,
        trades: Sequence[Trade],
        equity_curve: Sequence[tuple],
    ) -> PerformanceMetrics:
        """거래 목록과 자본 곡선으로 성과 지표를 계산한다."""
        if not equity_curve:
            return _empty_metrics()

        _validate_intervals(equity_curve)

        total_return = _calc_total_return(equity_curve)
        max_drawdown = _calc_max_drawdown(equity_curve)
        sharpe = self._calc_sharpe(equity_curve)
        win_rate = _calc_win_rate(trades)

        return PerformanceMetrics(
            total_return=total_return,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
        )

    def _calc_sharpe(self, equity_curve: Sequence[tuple]) -> float:
        """초과수익률 기반 연율화 샤프 비율.

        WHY: risk_free_rate 를 self 에서 읽어 일별 차감하므로
             동일 인스턴스에서 일관된 무위험 수익률 기준을 유지한다.
             ddof=1 (표본 표준편차) 로 소표본 편향을 줄인다.
        """
        values = [float(v) for _, v in equity_curve]
        if len(values) < 2:
            return 0.0

        daily_rfr = self.risk_free_rate / TRADING_DAYS_PER_YEAR
        returns = [
            (values[i] - values[i - 1]) / values[i - 1]
            for i in range(1, len(values))
            if values[i - 1] != 0.0
        ]
        excess = [r - daily_rfr for r in returns]

        return _sharpe_from_excess(excess)


# ---------------------------------------------------------------------------
# 내부 순수 함수
# ---------------------------------------------------------------------------

def _validate_intervals(equity_curve: Sequence[tuple]) -> None:
    """등간격 timestamp 여부를 검증한다.

    WHY: 비등간격 데이터에서 단순 일별 공식을 쓰면 샤프가 왜곡되므로
         조용한 오답 대신 명시적 ValueError 로 사용자가 즉시 인지하게 한다.
         포인트 ≤ 1 이면 간격 자체가 없으므로 검증을 건너뛴다.
    """
    if len(equity_curve) <= 1:
        return

    timestamps = [ts for ts, _ in equity_curve]
    first_interval = timestamps[1] - timestamps[0]

    for i in range(2, len(timestamps)):
        interval = timestamps[i] - timestamps[i - 1]
        if interval != first_interval:
            raise ValueError(
                f"비등간격 equity_curve: index {i - 1}→{i} 간격 {interval} ≠ 기준 {first_interval}"
            )


def _sharpe_from_excess(excess: list[float]) -> float:
    """초과수익률 리스트에서 연율화 샤프 비율을 계산한다.

    WHY: ddof=1 분모=(n-1) 이므로 n<2 이면 분모=0 → 0.0 반환으로 안전 처리한다.
    """
    n = len(excess)
    if n < 2:
        return 0.0

    mean_e = sum(excess) / n
    # ddof=1: 비편향 표본 표준편차
    variance = sum((e - mean_e) ** 2 for e in excess) / (n - 1)
    std_e = math.sqrt(variance)

    if std_e == 0.0:
        return 0.0
    return (mean_e / std_e) * _ANNUALIZATION_FACTOR


def _empty_metrics() -> PerformanceMetrics:
    """입력 없을 때 기본 지표를 반환한다."""
    return PerformanceMetrics(
        total_return=_ZERO,
        sharpe=0.0,
        max_drawdown=_ZERO,
        win_rate=0.0,
    )


def _calc_total_return(equity_curve: Sequence[tuple]) -> Decimal:
    """total_return = (final - initial) / initial."""
    initial = equity_curve[0][1]
    final = equity_curve[-1][1]
    if initial == _ZERO:
        return _ZERO
    return (final - initial) / initial


def _calc_max_drawdown(equity_curve: Sequence[tuple]) -> Decimal:
    """최대낙폭(MDD) = min( (trough - peak) / peak ) 또는 0.

    WHY: peak 대비 얼마나 하락했는지를 비율로 측정해야
         자본 규모와 무관하게 비교 가능한 위험 지표가 된다.
    """
    peak = equity_curve[0][1]
    max_dd = _ZERO
    for _, value in equity_curve:
        if value > peak:
            peak = value
        if peak != _ZERO:
            drawdown = (value - peak) / peak
            if drawdown < max_dd:
                max_dd = drawdown
    return max_dd


def _calc_win_rate(trades: Sequence[Trade]) -> float:
    """승률 = pnl > 0 인 거래 수 / 전체 거래 수."""
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.pnl > _ZERO)
    return wins / len(trades)
