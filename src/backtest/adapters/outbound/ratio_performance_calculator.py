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

# 연율화 인수 (일별 수익률 기준 252 거래일)
_ANNUALIZATION_FACTOR = math.sqrt(252)

_ZERO = Decimal("0")
_ONE = Decimal("1")


class RatioPerformanceCalculator:
    """샤프 비율·MDD·승률·총 수익률을 계산하는 PerformanceCalculator 어댑터."""

    def compute(
        self,
        trades: Sequence[Trade],
        equity_curve: Sequence[tuple],
    ) -> PerformanceMetrics:
        """거래 목록과 자본 곡선으로 성과 지표를 계산한다."""
        if not equity_curve:
            return _empty_metrics()

        total_return = _calc_total_return(equity_curve)
        max_drawdown = _calc_max_drawdown(equity_curve)
        # WHY: Decimal → float 변환은 샤프 계산 내부로만 제한한다.
        sharpe = _calc_sharpe(equity_curve)
        win_rate = _calc_win_rate(trades)

        return PerformanceMetrics(
            total_return=total_return,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
        )


# ---------------------------------------------------------------------------
# 내부 순수 함수
# ---------------------------------------------------------------------------

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


def _calc_sharpe(equity_curve: Sequence[tuple]) -> float:
    """샤프 비율 = mean(daily_returns) / std(daily_returns) * sqrt(252).

    WHY: Decimal → float 변환 경계를 이 함수 내부로만 제한한다.
         분산이 0이면 ZeroDivisionError 대신 0.0을 반환해 안전성을 보장한다.

    M2 한정 단순화: equity_curve 등간격 가정, 무위험 수익률 차감 없음.
    정식 구현(실제 trading day 간격, 무위험 수익률 차감)은 M3 예정.
    """
    values = [float(v) for _, v in equity_curve]
    if len(values) < 2:
        return 0.0

    returns = [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values)) if values[i - 1] != 0.0]
    if not returns:
        return 0.0

    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
    std_r = math.sqrt(variance)

    if std_r == 0.0:
        return 0.0
    return (mean_r / std_r) * _ANNUALIZATION_FACTOR


def _calc_win_rate(trades: Sequence[Trade]) -> float:
    """승률 = pnl > 0 인 거래 수 / 전체 거래 수."""
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.pnl > _ZERO)
    return wins / len(trades)
