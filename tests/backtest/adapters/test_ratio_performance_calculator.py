"""
RatioPerformanceCalculator 어댑터 단위 테스트 (TDD RED 단계).

WHY: PerformanceCalculator 포트의 구체 구현이 샤프 비율, MDD, 승률,
     총 수익률을 수기 계산과 일치하는지 검증한다.
     구현 전에는 ModuleNotFoundError 로 RED 상태가 된다.

어댑터 시그니처 (Protocol 보다 확장):
    compute(trades: Sequence[Trade], equity_curve: Sequence[tuple[datetime, Decimal]]) -> PerformanceMetrics

WHY 확장 시그니처: PerformanceCalculator Protocol 은 (trades, equity_curve) 로
     정의되어 있어 어댑터가 동일 시그니처를 사용한다.
     equity_curve 는 (datetime, Decimal) 튜플 시퀀스로 자본 곡선을 전달한다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backtest.domain.trade import Trade


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _utc(year: int, month: int, day: int) -> datetime:
    """UTC tz-aware datetime 생성 헬퍼."""
    return datetime(year, month, day, tzinfo=timezone.utc)


def _trade(pnl: str, entry_day: int = 1, exit_day: int = 2) -> Trade:
    """테스트용 Trade 생성 헬퍼."""
    return Trade(
        ticker="AAPL",
        entry_time=_utc(2024, 1, entry_day),
        exit_time=_utc(2024, 1, exit_day),
        entry_price=Decimal("100"),
        exit_price=Decimal("110"),
        quantity=Decimal("1"),
        pnl=Decimal(pnl),
    )


def _equity(*values: str) -> list[tuple[datetime, Decimal]]:
    """자본 곡선 [(datetime, Decimal), ...] 생성 헬퍼."""
    return [
        (_utc(2024, 1, i + 1), Decimal(v))
        for i, v in enumerate(values)
    ]


# ---------------------------------------------------------------------------
# 테스트 클래스
# ---------------------------------------------------------------------------

class TestRatioPerformanceCalculator_임포트:
    """어댑터 임포트 가능 여부."""

    def test_어댑터를_임포트할_수_있다(self) -> None:
        """WHY: 파일 미존재·문법 오류를 CI 에서 조기 감지한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import (  # noqa: F401
            RatioPerformanceCalculator,
        )

    def test_인스턴스를_생성할_수_있다(self) -> None:
        """WHY: 기본 생성자가 인자 없이 동작해야 조립이 쉽다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator
        calc = RatioPerformanceCalculator()
        assert calc is not None


class TestRatioPerformanceCalculator_빈_입력:
    """빈 trades/equity 입력 → 기본값 반환."""

    def test_빈_입력이면_모든_지표가_기본값이다(self) -> None:
        """WHY: 거래가 전혀 없는 경우 나누기 0 예외 없이 안전하게 기본값을 반환해야 한다.
               total_return=0, sharpe=0.0, max_drawdown=0, win_rate=0.0"""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        result = calc.compute(trades=[], equity_curve=[])

        assert result.total_return == Decimal("0")
        assert result.sharpe == 0.0
        assert result.max_drawdown == Decimal("0")
        assert result.win_rate == 0.0


class TestRatioPerformanceCalculator_max_drawdown:
    """최대 낙폭(MDD) 계산 케이스."""

    def test_단조_증가_equity이면_max_drawdown이_0이다(self) -> None:
        """WHY: 한 번도 하락하지 않은 자본 곡선의 MDD = 0 이어야 한다.
               음수 MDD 반환은 설계 오류를 의미한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        equity = _equity("100", "110", "120", "130")
        result = calc.compute(trades=[], equity_curve=equity)

        # MDD 는 0 또는 Decimal("0") 이어야 한다
        assert result.max_drawdown == Decimal("0")

    def test_peak_to_trough_equity에서_mdd가_수계산과_일치한다(self) -> None:
        """WHY: 100→80→90 자본 곡선의 MDD = (80-100)/100 = -0.2 여야 한다.
               수기 검증으로 공식이 올바름을 확인한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        # peak=100, trough=80, recovery=90 → MDD = -0.2
        equity = _equity("100", "80", "90")
        result = calc.compute(trades=[], equity_curve=equity)

        # MDD = (80 - 100) / 100 = -0.2
        assert result.max_drawdown == Decimal("-0.2")


class TestRatioPerformanceCalculator_total_return:
    """총 수익률 계산 케이스."""

    def test_total_return이_수계산과_일치한다(self) -> None:
        """WHY: total_return = (final - initial) / initial 공식 준수 확인.
               100 → 120 이면 0.2 (20%)."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        equity = _equity("100", "110", "120")
        result = calc.compute(trades=[], equity_curve=equity)

        # (120 - 100) / 100 = 0.2
        expected = Decimal("0.2")
        assert result.total_return == expected


class TestRatioPerformanceCalculator_win_rate:
    """승률 계산 케이스."""

    def test_3거래_중_2승이면_win_rate가_2_3이다(self) -> None:
        """WHY: win_rate = 수익 거래 수 / 전체 거래 수.
               pnl > 0 인 거래만 승리로 간주한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        trades = [
            _trade(pnl="100", exit_day=2),    # 승
            _trade(pnl="200", exit_day=3),    # 승
            _trade(pnl="-50", exit_day=4),    # 패
        ]
        result = calc.compute(trades=trades, equity_curve=_equity("100", "200", "400", "350"))

        expected = 2 / 3
        assert abs(result.win_rate - expected) < 1e-9


class TestRatioPerformanceCalculator_sharpe:
    """샤프 비율 계산 케이스."""

    def test_분산이_0이면_sharpe가_0이다(self) -> None:
        """WHY: 모든 기간 수익률이 동일하면 표준편차=0 → 나누기 0 방지로 0.0 반환.
               ZeroDivisionError 가 아닌 안전한 처리를 보장한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        # 매일 동일 자본 → 수익률 = 0 연속 → std = 0
        equity = _equity("100", "100", "100", "100")
        result = calc.compute(trades=[], equity_curve=equity)

        assert result.sharpe == 0.0

    def test_일정_양수_수익률이면_sharpe가_양수_float이다(self) -> None:
        """WHY: 매 기간 동일한 양수 수익률이면 샤프 비율이 양수여야 한다.
               반환 타입이 float 인지도 함께 확인한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        # 100→110→121→133.1: 매 기간 10% 수익률
        equity = _equity("100", "110", "121", "133.1")
        result = calc.compute(trades=[], equity_curve=equity)

        assert isinstance(result.sharpe, float)
        assert result.sharpe > 0.0
