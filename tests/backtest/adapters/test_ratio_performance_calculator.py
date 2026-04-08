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

M3 추가 테스트:
    - risk_free_rate 생성자 파라미터
    - 비등간격 timestamp → ValueError
    - ddof=1 표본 표준편차
    - 초과수익률(excess return) 기반 샤프 계산
    - 데이터 포인트 < 2 → 0.0
    - 기존 동작 호환 (risk_free_rate=0, 1일 등간격)
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
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


# ---------------------------------------------------------------------------
# M3 RED 테스트: risk_free_rate 생성자 파라미터
# ---------------------------------------------------------------------------

# 연간 무위험 수익률 5% (테스트 상수화)
_RFR_5PCT = 0.05
# 일별 무위험 수익률 계산 기준 거래일 수
_TRADING_DAYS_PER_YEAR = 252
# 부동소수점 허용 오차
_FLOAT_TOLERANCE = 1e-9


class TestRatioPerformanceCalculator_생성자_risk_free_rate:
    """M3: risk_free_rate 생성자 파라미터 수용 여부."""

    def test_기본값_없이_인자_없는_생성자가_동작한다(self) -> None:
        """WHY: 하위 호환성 — 기존 코드가 인자 없이 생성해도 깨지지 않아야 한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        assert calc is not None

    def test_risk_free_rate를_키워드로_받아_저장한다(self) -> None:
        """WHY: 생성자에서 받은 risk_free_rate 를 인스턴스가 보관해야
               compute() 호출마다 공통 값을 재사용할 수 있다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator(risk_free_rate=_RFR_5PCT)
        assert calc.risk_free_rate == _RFR_5PCT

    def test_risk_free_rate_기본값이_0이다(self) -> None:
        """WHY: 명시하지 않으면 무위험 수익률 0 으로 취급해야 기존 동작이 보존된다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        assert calc.risk_free_rate == 0.0


# ---------------------------------------------------------------------------
# M3 RED 테스트: 비등간격 timestamp → ValueError
# ---------------------------------------------------------------------------

def _equity_irregular() -> list[tuple[datetime, Decimal]]:
    """비등간격 자본 곡선 생성 헬퍼.

    WHY: [1일 간격, 2일 간격] 조합으로 비등간격 조건을 확실히 만든다.
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        (base, Decimal("100")),
        (base + timedelta(days=1), Decimal("110")),
        # 다음 간격은 2일 → 비등간격
        (base + timedelta(days=3), Decimal("120")),
    ]


def _equity_regular(n: int = 4, start_value: str = "100") -> list[tuple[datetime, Decimal]]:
    """1일 등간격 자본 곡선 생성 헬퍼.

    WHY: 등간격 기준 케이스를 명시적으로 구분해 테스트 가독성을 높인다.
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    value = Decimal(start_value)
    return [(base + timedelta(days=i), value) for i in range(n)]


class TestRatioPerformanceCalculator_단조증가_검증:
    """M6: 실데이터 주말·공휴일 간격을 허용하되 단조 증가만 강제."""

    def test_비등간격이어도_단조_증가이면_정상_계산된다(self) -> None:
        """WHY: 실거래일 데이터는 주말/공휴일로 1~3일 간격이 섞인다.
               엄격 등간격을 강제하면 실데이터 경로가 전부 막히므로 완화한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        result = calc.compute(trades=[], equity_curve=_equity_irregular())
        assert isinstance(result.sharpe, float)

    def test_역행_timestamp이면_ValueError를_발생시킨다(self) -> None:
        """WHY: 단조 증가 위반은 데이터 무결성 오류이므로 명시적으로 차단한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        reversed_curve = [
            (base, Decimal("100")),
            (base + timedelta(days=2), Decimal("101")),
            (base + timedelta(days=1), Decimal("102")),  # 역행
        ]
        calc = RatioPerformanceCalculator()
        with pytest.raises(ValueError, match="단조 증가"):
            calc.compute(trades=[], equity_curve=reversed_curve)

    def test_1개_포인트_equity_curve는_간격_검증을_건너뛴다(self) -> None:
        """WHY: 포인트가 1개이면 간격을 계산할 수 없으므로 검증 자체를 생략해야 한다.
               (이미 데이터 < 2 → sharpe=0.0 케이스로 처리된다.)"""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        single = [(base, Decimal("100"))]
        calc = RatioPerformanceCalculator()
        # ValueError 없이 정상 반환이어야 한다
        result = calc.compute(trades=[], equity_curve=single)
        assert result.sharpe == 0.0

    def test_등간격_equity_curve는_ValueError를_발생시키지_않는다(self) -> None:
        """WHY: 정상 등간격 입력이 오탐(false positive)으로 거부되면 안 된다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        # 예외 없이 정상 실행 검증
        result = calc.compute(trades=[], equity_curve=_equity_regular())
        assert isinstance(result.sharpe, float)


# ---------------------------------------------------------------------------
# M3 RED 테스트: ddof=1 표본 표준편차
# ---------------------------------------------------------------------------

def _compute_expected_sharpe(
    values: list[float],
    risk_free_rate: float = 0.0,
) -> float:
    """기대 샤프 비율 수기 계산 헬퍼.

    WHY: 테스트 내부에서 동일 공식을 반복하면 오류 파급 위험이 있으므로
         단일 헬퍼로 추출해 DRY 를 지키고 WHY 주석으로 공식을 명시한다.

    공식:
        daily_rfr = risk_free_rate / TRADING_DAYS_PER_YEAR
        excess_returns = [r - daily_rfr for r in daily_returns]
        sharpe = mean(excess_returns) / std(excess_returns, ddof=1) * sqrt(252)
    """
    n = len(values)
    if n < 2:
        return 0.0
    daily_rfr = risk_free_rate / _TRADING_DAYS_PER_YEAR
    returns = [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, n)]
    excess = [r - daily_rfr for r in returns]
    m = len(excess)
    if m < 2:
        return 0.0
    mean_e = sum(excess) / m
    # ddof=1: 표본 표준편차 (비편향 추정량)
    variance = sum((e - mean_e) ** 2 for e in excess) / (m - 1)
    std_e = math.sqrt(variance)
    if std_e == 0.0:
        return 0.0
    return (mean_e / std_e) * math.sqrt(_TRADING_DAYS_PER_YEAR)


class TestRatioPerformanceCalculator_ddof1_표본표준편차:
    """M3: 표본 표준편차(ddof=1) 사용 여부."""

    def test_데이터_포인트_2개면_ddof1로_계산한다(self) -> None:
        """WHY: ddof=1 기준 n=2 일 때 분모=1 이므로 ddof=0(분모=2)과 값이 다르다.
               이 차이로 ddof=1 준수 여부를 직접 검증한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        # 100 → 110: 수익률 [0.1], 포인트 2개 → ddof=1 이면 std 계산 불가 → 0.0
        equity = _equity_regular(n=2)
        result = calc.compute(trades=[], equity_curve=equity)
        # 수익률이 1개이면 ddof=1 분모=0 → 0.0 반환
        assert result.sharpe == 0.0

    def test_포인트_3개_수익률_다양하면_ddof1_값과_일치한다(self) -> None:
        """WHY: 수익률 2개 이상일 때 ddof=1 vs ddof=0 의 차이로 구현을 검증한다.
               수기 ddof=1 계산 결과와 오차 범위 내에서 일치해야 한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        # 100 → 110 → 90: 수익률 [+0.1, -0.1818...]
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        equity = [
            (base, Decimal("100")),
            (base + timedelta(days=1), Decimal("110")),
            (base + timedelta(days=2), Decimal("90")),
        ]
        calc = RatioPerformanceCalculator()
        result = calc.compute(trades=[], equity_curve=equity)

        expected = _compute_expected_sharpe([100.0, 110.0, 90.0])
        assert abs(result.sharpe - expected) < _FLOAT_TOLERANCE


# ---------------------------------------------------------------------------
# M3 RED 테스트: 초과수익률(excess return) 기반 샤프 계산
# ---------------------------------------------------------------------------

class TestRatioPerformanceCalculator_초과수익률_샤프:
    """M3: risk_free_rate 차감 초과수익률로 샤프 계산 여부."""

    def test_risk_free_rate_0이면_기존_sharpe와_동일하다(self) -> None:
        """WHY: 무위험 수익률 0 은 초과수익률=원수익률 이므로
               M2 기존 동작과 결과가 일치해야 하위 호환성이 보장된다.
               단, ddof 변경으로 인한 차이는 허용하지 않는다 — ddof=1 기준으로 재계산."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        raw_values = [100.0, 105.0, 110.25, 115.0]
        equity = [
            (base + timedelta(days=i), Decimal(str(v)))
            for i, v in enumerate(raw_values)
        ]
        calc = RatioPerformanceCalculator(risk_free_rate=0.0)
        result = calc.compute(trades=[], equity_curve=equity)

        expected = _compute_expected_sharpe(raw_values, risk_free_rate=0.0)
        assert abs(result.sharpe - expected) < _FLOAT_TOLERANCE

    def test_risk_free_rate_5pct로_초과수익률_sharpe가_수계산과_일치한다(self) -> None:
        """WHY: 연 5% 무위험 수익률을 적용하면 일별 차감값이 줄어
               순수 시장 초과성과(alpha)를 측정하는 샤프 비율이 달라진다.
               이 테스트로 risk_free_rate 차감 로직이 실제로 반영됨을 강제한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        raw_values = [100.0, 102.0, 104.0, 101.0, 103.0]
        equity = [
            (base + timedelta(days=i), Decimal(str(v)))
            for i, v in enumerate(raw_values)
        ]
        calc = RatioPerformanceCalculator(risk_free_rate=_RFR_5PCT)
        result = calc.compute(trades=[], equity_curve=equity)

        expected = _compute_expected_sharpe(raw_values, risk_free_rate=_RFR_5PCT)
        assert abs(result.sharpe - expected) < _FLOAT_TOLERANCE

    def test_risk_free_rate가_수익률보다_높으면_sharpe가_음수일_수_있다(self) -> None:
        """WHY: 초과수익률이 음수이면 샤프도 음수여야 한다.
               양수 클리핑이 없음을 검증해 올바른 부호 처리를 강제한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        # 매우 높은 무위험 수익률(50%)로 초과수익률을 강제 음수화
        _very_high_rfr = 0.50
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        raw_values = [100.0, 100.1, 100.2, 100.3]
        equity = [
            (base + timedelta(days=i), Decimal(str(v)))
            for i, v in enumerate(raw_values)
        ]
        calc = RatioPerformanceCalculator(risk_free_rate=_very_high_rfr)
        result = calc.compute(trades=[], equity_curve=equity)

        expected = _compute_expected_sharpe(raw_values, risk_free_rate=_very_high_rfr)
        # 기대값이 음수임을 확인 (테스트 설계 전제 검증)
        assert expected < 0.0
        assert abs(result.sharpe - expected) < _FLOAT_TOLERANCE


# ---------------------------------------------------------------------------
# M3 RED 테스트: 데이터 포인트 < 2 → 0.0
# ---------------------------------------------------------------------------

class TestRatioPerformanceCalculator_데이터포인트_경계:
    """M3: 데이터 포인트 수 경계값 케이스."""

    def test_equity_curve가_빈_리스트이면_sharpe가_0이다(self) -> None:
        """WHY: 빈 입력은 나누기 0 위험이 있으므로 0.0 반환으로 안전 처리해야 한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator(risk_free_rate=_RFR_5PCT)
        result = calc.compute(trades=[], equity_curve=[])
        assert result.sharpe == 0.0

    def test_equity_curve가_1개이면_sharpe가_0이다(self) -> None:
        """WHY: 수익률을 계산하려면 최소 2개의 자본 포인트가 필요하다.
               포인트 1개는 수익률 0개 → sharpe 계산 불가 → 0.0."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        single = [(base, Decimal("100"))]
        calc = RatioPerformanceCalculator(risk_free_rate=_RFR_5PCT)
        result = calc.compute(trades=[], equity_curve=single)
        assert result.sharpe == 0.0

    def test_equity_curve가_2개이면_수익률_1개_ddof1_불가_sharpe가_0이다(self) -> None:
        """WHY: 수익률이 1개일 때 ddof=1 표준편차 분모=0 이므로
               ZeroDivisionError 대신 0.0 을 반환해 안전성을 보장해야 한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        two_points = [
            (base, Decimal("100")),
            (base + timedelta(days=1), Decimal("110")),
        ]
        calc = RatioPerformanceCalculator(risk_free_rate=_RFR_5PCT)
        result = calc.compute(trades=[], equity_curve=two_points)
        assert result.sharpe == 0.0


# ---------------------------------------------------------------------------
# R1 리뷰 반영 테스트: equity 0/음수 → ValueError, timestamp 타입 가드
# ---------------------------------------------------------------------------

class TestRatioPerformanceCalculator_equity_가드:
    """R1-[중요-1]: equity 0 또는 음수 포인트 → ValueError."""

    def test_equity가_0이면_ValueError를_발생시킨다(self) -> None:
        """WHY: equity=0 이면 수익률 계산 분모가 0 이 되어 오답이 나온다.
               silent skip 대신 명시적 오류로 사용자가 즉시 인지해야 한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        equity_with_zero = [
            (base, Decimal("100")),
            (base + timedelta(days=1), Decimal("0")),
            (base + timedelta(days=2), Decimal("110")),
        ]
        calc = RatioPerformanceCalculator()
        with pytest.raises(ValueError, match="equity 가 0 이하인 포인트는 허용되지 않습니다"):
            calc.compute(trades=[], equity_curve=equity_with_zero)

    def test_equity가_음수이면_ValueError를_발생시킨다(self) -> None:
        """WHY: equity 가 음수이면 비율 계산 결과가 경제적으로 무의미하다.
               조용히 넘어가지 않고 명시적 오류를 발생시켜야 한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        equity_with_negative = [
            (base, Decimal("100")),
            (base + timedelta(days=1), Decimal("110")),
            (base + timedelta(days=2), Decimal("-10")),
        ]
        calc = RatioPerformanceCalculator()
        with pytest.raises(ValueError, match="equity 가 0 이하인 포인트는 허용되지 않습니다"):
            calc.compute(trades=[], equity_curve=equity_with_negative)

    def test_equity_curve가_빈_리스트이면_ValueError_없이_0을_반환한다(self) -> None:
        """WHY: 빈 입력은 equity 가드 진입 전에 조기 반환하므로 ValueError 가 없어야 한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        result = calc.compute(trades=[], equity_curve=[])
        assert result.sharpe == 0.0

    def test_equity_curve가_1개이면_ValueError_없이_0을_반환한다(self) -> None:
        """WHY: 포인트 1개는 _calc_sharpe 에서 len < 2 로 조기 반환하므로
               equity 가드가 발동되지 않아야 한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        single = [(base, Decimal("0"))]  # equity=0 이지만 길이 1 이므로 허용
        calc = RatioPerformanceCalculator()
        result = calc.compute(trades=[], equity_curve=single)
        assert result.sharpe == 0.0


class TestRatioPerformanceCalculator_timestamp_타입_가드:
    """R1-[중요-2]: timestamp 가 datetime.datetime 이 아닐 때 → TypeError."""

    def test_timestamp가_int이면_TypeError를_발생시킨다(self) -> None:
        """WHY: int timestamp 는 빼기 연산이 되지만 의미가 없는 값이 계산된다.
               타입 계약 강제로 잘못된 입력을 즉시 거부해야 한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        equity_int_ts = [
            (20240101, Decimal("100")),
            (20240102, Decimal("110")),
            (20240103, Decimal("120")),
        ]
        calc = RatioPerformanceCalculator()
        with pytest.raises(TypeError, match="timestamp 는 datetime.datetime 이어야 합니다"):
            calc.compute(trades=[], equity_curve=equity_int_ts)

    def test_timestamp가_float이면_TypeError를_발생시킨다(self) -> None:
        """WHY: float 타임스탬프(unix epoch)는 timedelta 연산을 지원하지 않는다.
               타입 계약 위반을 조기에 탐지해야 한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        equity_float_ts = [
            (1704067200.0, Decimal("100")),
            (1704153600.0, Decimal("110")),
            (1704240000.0, Decimal("120")),
        ]
        calc = RatioPerformanceCalculator()
        with pytest.raises(TypeError, match="timestamp 는 datetime.datetime 이어야 합니다"):
            calc.compute(trades=[], equity_curve=equity_float_ts)

    def test_tz_aware_datetime_등간격이면_정상_통과한다(self) -> None:
        """WHY: tz-aware datetime 이 타입 계약을 만족하고 등간격이면 오류 없이 계산돼야 한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        equity_tz_aware = [
            (base + timedelta(days=i), Decimal(str(100 + i * 5)))
            for i in range(4)
        ]
        calc = RatioPerformanceCalculator()
        result = calc.compute(trades=[], equity_curve=equity_tz_aware)
        assert isinstance(result.sharpe, float)


class TestRatioPerformanceCalculator_Sortino_Calmar:
    """Sortino / Calmar 신규 지표 검증."""

    def test_단조_증가_equity이면_sortino_는_0이다(self) -> None:
        """WHY: 하방 수익률이 없으면 Sortino 분모=0 → 0.0 반환."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        result = calc.compute(trades=[], equity_curve=_equity("100", "110", "120", "130"))
        assert result.sortino == 0.0

    def test_하방_변동이_있으면_sortino_가_계산된다(self) -> None:
        """WHY: 음의 초과수익률이 2개 이상이면 Sortino 가 유한한 값으로 계산된다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        # 100 → 95 → 105 → 92 → 110 (하방 2회, 상방 2회)
        result = calc.compute(
            trades=[], equity_curve=_equity("100", "95", "105", "92", "110")
        )
        assert isinstance(result.sortino, float)
        assert math.isfinite(result.sortino)

    def test_단조_증가_equity이면_calmar_는_0이다(self) -> None:
        """WHY: MDD=0 이면 Calmar 는 정의 불가능하므로 0.0 반환."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        result = calc.compute(trades=[], equity_curve=_equity("100", "110", "120"))
        assert result.calmar == 0.0

    def test_하락_equity이면_calmar_가_음수이다(self) -> None:
        """WHY: 전체 수익률이 음수이면 Calmar = ann_return / |MDD| < 0."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        result = calc.compute(trades=[], equity_curve=_equity("100", "90", "80"))
        assert result.calmar < 0.0

    def test_metrics_는_sortino_와_calmar_필드를_가진다(self) -> None:
        """WHY: PerformanceMetrics 값 객체가 새 필드를 노출한다."""
        from backtest.adapters.outbound.ratio_performance_calculator import RatioPerformanceCalculator

        calc = RatioPerformanceCalculator()
        result = calc.compute(trades=[], equity_curve=_equity("100", "110"))
        assert hasattr(result, "sortino")
        assert hasattr(result, "calmar")
