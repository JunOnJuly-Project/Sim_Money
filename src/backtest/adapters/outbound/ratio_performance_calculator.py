"""
비율 기반 성과 지표 계산기 어댑터.

WHY: 총 수익률·샤프 비율·MDD·승률은 모두 비율(ratio) 지표이므로
     이 어댑터에서 일관된 공식으로 계산한다.
     Decimal → float 변환은 이 경계 내부에서만 발생하도록 제한한다.

타입 계약:
    - equity_curve 의 timestamp 는 반드시 datetime.datetime 이어야 한다.
    - tz-naive/aware 혼합은 허용하지 않는다. 동일 타입 datetime 만 지원한다.
"""
from __future__ import annotations

import datetime
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
        sortino = self._calc_sortino(equity_curve)
        calmar = _calc_calmar(total_return, max_drawdown, len(equity_curve))
        win_rate = _calc_win_rate(trades)

        return PerformanceMetrics(
            total_return=total_return,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            sortino=sortino,
            calmar=calmar,
        )

    def _calc_sortino(self, equity_curve: Sequence[tuple]) -> float:
        """하방 변동성 기반 연율화 Sortino 비율.

        WHY: Sharpe 는 전체 변동성을 처벌하지만 Sortino 는 하방 수익률만
             처벌해 실제 투자자가 느끼는 "손실 위험"에 더 부합한다.
        """
        values = [float(v) for _, v in equity_curve]
        if len(values) < 2:
            return 0.0
        _validate_equity_values(values)

        daily_rfr = self.risk_free_rate / TRADING_DAYS_PER_YEAR
        returns = [
            (values[i] - values[i - 1]) / values[i - 1]
            for i in range(1, len(values))
        ]
        excess = [r - daily_rfr for r in returns]
        return _sortino_from_excess(excess)

    def _calc_sharpe(self, equity_curve: Sequence[tuple]) -> float:
        """초과수익률 기반 연율화 샤프 비율.

        WHY: risk_free_rate 를 self 에서 읽어 일별 차감하므로
             동일 인스턴스에서 일관된 무위험 수익률 기준을 유지한다.
             ddof=1 (표본 표준편차) 로 소표본 편향을 줄인다.

        Raises:
            ValueError: equity_curve 에 0 이하 equity 포인트가 있을 때.
                        단, 길이 0 또는 1 인 경우는 0.0 반환으로 조기 탈출한다.
        """
        values = [float(v) for _, v in equity_curve]
        if len(values) < 2:
            return 0.0

        _validate_equity_values(values)

        daily_rfr = self.risk_free_rate / TRADING_DAYS_PER_YEAR
        returns = [
            (values[i] - values[i - 1]) / values[i - 1]
            for i in range(1, len(values))
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

    타입 계약:
        - timestamp 는 datetime.datetime 이어야 한다.
        - tz-naive/aware 혼합은 허용하지 않는다. 동일 타입 datetime 만 지원한다.

    Raises:
        TypeError: 첫 포인트의 timestamp 가 datetime.datetime 이 아닐 때.
        ValueError: timestamp 간격이 불균일할 때.
    """
    if len(equity_curve) <= 1:
        return

    timestamps = [ts for ts, _ in equity_curve]

    # WHY: 타입 계약 강제 — 잘못된 타입이 조용히 연산되어 오답을 내는 것을 방지한다.
    if not isinstance(timestamps[0], datetime.datetime):
        raise TypeError("timestamp 는 datetime.datetime 이어야 합니다")

    first_interval = timestamps[1] - timestamps[0]

    for i in range(2, len(timestamps)):
        interval = timestamps[i] - timestamps[i - 1]
        if interval != first_interval:
            raise ValueError(
                f"비등간격 equity_curve: index {i - 1}→{i} 간격 {interval} ≠ 기준 {first_interval}"
            )


def _validate_equity_values(values: list[float]) -> None:
    """equity 값이 모두 양수인지 검증한다.

    WHY: equity 가 0 이하이면 로그 수익률 / 비율 계산이 무의미하거나 오답이 된다.
         silent skip(if values[i-1] != 0) 대신 명시적 오류로 사용자가 즉시 인지하게 한다.

    Raises:
        ValueError: 0 이하 equity 포인트가 하나라도 존재할 때.
    """
    for v in values:
        if v <= 0.0:
            raise ValueError("샤프 계산: equity 가 0 이하인 포인트는 허용되지 않습니다")


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


def _sortino_from_excess(excess: list[float]) -> float:
    """초과수익률 중 음수만으로 하방 표준편차를 계산해 연율화한다.

    WHY: 하방 수익률이 없거나 n<2 이면 분모=0 이 되므로 0.0 반환.
    """
    n = len(excess)
    if n < 2:
        return 0.0
    mean_e = sum(excess) / n
    downside = [e for e in excess if e < 0.0]
    if len(downside) < 2:
        return 0.0
    # WHY: 하방 편차의 제곱 평균. ddof=1 로 편향을 줄인다.
    variance = sum(d ** 2 for d in downside) / (len(downside) - 1)
    downside_std = math.sqrt(variance)
    if downside_std == 0.0:
        return 0.0
    return (mean_e / downside_std) * _ANNUALIZATION_FACTOR


def _calc_calmar(
    total_return: Decimal, max_drawdown: Decimal, num_points: int
) -> float:
    """Calmar = 연율화 수익률 / |MDD|.

    WHY: MDD 대비 연수익률로 꼬리 리스크 조정 수익률을 표현한다.
         num_points<2 또는 MDD=0 이면 0.0 을 반환해 안전하게 처리한다.
    """
    if num_points < 2 or max_drawdown == _ZERO:
        return 0.0
    # (1 + total_return) ^ (252 / (num_points - 1)) - 1
    periods = TRADING_DAYS_PER_YEAR / (num_points - 1)
    base = 1.0 + float(total_return)
    if base <= 0.0:
        return 0.0
    annualized = base ** periods - 1.0
    return annualized / abs(float(max_drawdown))


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
