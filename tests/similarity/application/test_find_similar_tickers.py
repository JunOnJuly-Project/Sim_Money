"""
FindSimilarTickers 유스케이스 TDD RED 단계 테스트.

WHY: 헥사고날 아키텍처에서 유스케이스는 포트(인터페이스)에만 의존해야 한다.
     인메모리 Fake 구현으로 포트 계약을 검증하고, 유스케이스의 모든 분기를
     외부 인프라 없이 결정론적으로 테스트한다.

     이 파일은 RED 단계 — FindSimilarTickers 구현이 없으므로
     ImportError 가 기대된다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import pytest

# RED: 아래 임포트는 아직 구현이 없으므로 ImportError 가 발생해야 한다.
from similarity.application.find_similar_tickers import (
    FindSimilarQuery,
    FindSimilarTickers,
    SimilarityResult,
)
from market_data.application.ports import PriceRepository
from market_data.domain.adjusted_price import AdjustedPrice
from market_data.domain.market import Market
from market_data.domain.price_series import PriceSeries
from market_data.domain.ticker import Ticker
from universe.domain.universe_snapshot import UniverseSnapshot


# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------

def _ticker(symbol: str, market: Market = Market.KRX) -> Ticker:
    """테스트 전용 Ticker 생성 헬퍼."""
    return Ticker(market=market, symbol=symbol)


def _make_series(
    ticker: Ticker,
    prices: list[float],
    start: date = date(2024, 1, 2),
) -> PriceSeries:
    """연속 날짜 기반 PriceSeries 생성 헬퍼.

    WHY: 개별 테스트가 날짜 계산 세부사항을 반복하지 않도록 추출한다.
         주말을 무시하고 연속 달력일로 구성하므로 테스트 목적으로만 사용한다.
    """
    entries = tuple(
        (start + timedelta(days=i), AdjustedPrice(Decimal(str(p))))
        for i, p in enumerate(prices)
    )
    return PriceSeries(ticker=ticker, prices=entries)


def _make_universe(
    name: str,
    tickers: list[Ticker],
    as_of: date = date(2024, 6, 30),
) -> UniverseSnapshot:
    """UniverseSnapshot 생성 헬퍼."""
    return UniverseSnapshot(name=name, as_of=as_of, tickers=tuple(tickers))


# ---------------------------------------------------------------------------
# 결정론적 가격 시계열 팩토리 (로그수익률 기반)
# ---------------------------------------------------------------------------

def _geometric_series(
    ticker: Ticker,
    n: int,
    daily_return: float,
    base: float = 100.0,
    start: date = date(2024, 1, 2),
) -> PriceSeries:
    """일정 일별 수익률을 가지는 기하급수적 가격 시계열.

    WHY: 결정론적 수익률을 갖는 시계열을 만들면 strategy.compute 에 전달될
         log_returns 값을 미리 예측할 수 있어 테스트 검증이 용이하다.
    """
    prices = [base * ((1 + daily_return) ** i) for i in range(n)]
    return _make_series(ticker, prices, start)


# ---------------------------------------------------------------------------
# Fake 포트 구현
# ---------------------------------------------------------------------------

class FakeRepository:
    """PriceRepository 포트의 인메모리 테스트 더블.

    WHY: DuckDB 없이 load/save/latest_date 계약을 인메모리 dict 로 구현해
         유스케이스 포트 의존성을 빠르게 검증한다.
    """

    def __init__(self, data: dict[Ticker, PriceSeries] | None = None) -> None:
        # ticker → PriceSeries 매핑
        self._data: dict[Ticker, PriceSeries] = data or {}
        self.load_calls: list[Ticker] = []

    def save(self, series: PriceSeries) -> None:
        """저장을 인메모리 dict 에 기록한다."""
        self._data[series.ticker] = series

    def latest_date(self, ticker: Ticker) -> Optional[date]:
        """보유한 최신 날짜를 반환한다."""
        series = self._data.get(ticker)
        return series.latest_date() if series is not None else None

    def load(self, ticker: Ticker) -> Optional[PriceSeries]:
        """ticker 에 해당하는 PriceSeries 를 반환한다. 없으면 None."""
        self.load_calls.append(ticker)
        return self._data.get(ticker)


class FakeUniverseSource:
    """UniverseSource 포트의 인메모리 테스트 더블.

    WHY: 실제 데이터 소스 없이 UniverseSnapshot 을 주입해
         유스케이스의 유니버스 조회 로직을 검증한다.
    """

    def __init__(self, snapshot: UniverseSnapshot) -> None:
        self._snapshot = snapshot

    def fetch(self, name: str, as_of: date) -> UniverseSnapshot:
        """사전 주입된 스냅샷을 반환한다."""
        return self._snapshot


class FakeStrategy:
    """SimilarityStrategy 포트의 결정론적 테스트 더블.

    WHY: 실제 공식 계산 없이 미리 정해진 점수를 반환해
         필터링/정렬 로직만 격리해서 검증한다.
    """

    def __init__(self, score_map: dict[tuple[tuple[float, ...], tuple[float, ...]], float]) -> None:
        # (a_tuple, b_tuple) → score 매핑
        self._map = score_map

    def compute(self, a: list[float], b: list[float]) -> float:
        """미리 정해진 점수를 반환한다.

        WHY: 결정론적 반환으로 유사도 수치보다 필터/정렬 동작을 검증한다.
        """
        key = (tuple(a), tuple(b))
        if key in self._map:
            return self._map[key]
        # 매핑에 없으면 기본값 0.0
        return 0.0


class FakeConstantStrategy:
    """항상 고정된 점수를 반환하는 단순 전략.

    WHY: 점수 값보다 호출 여부나 개수를 검증할 때 사용한다.
    """

    def __init__(self, constant: float = 0.5) -> None:
        self._constant = constant
        self.call_count: int = 0

    def compute(self, a: list[float], b: list[float]) -> float:
        self.call_count += 1
        return self._constant


# ---------------------------------------------------------------------------
# 공통 픽스처용 종목 상수
# ---------------------------------------------------------------------------

_TARGET = _ticker("TARGET")
_PEER_A = _ticker("PEER_A")
_PEER_B = _ticker("PEER_B")
_PEER_C = _ticker("PEER_C")
_AS_OF = date(2024, 6, 30)

# 최소 2개 이상의 가격을 갖는 단순 시계열 (로그수익률 1개 이상)
_BASE_PRICES = [100.0, 101.0, 102.0, 103.0]


def _prices_with_offset(offset: float) -> list[float]:
    """종목별 고유한 가격 시계열 생성 헬퍼.

    WHY: 모든 피어가 동일한 _BASE_PRICES 를 공유하면 log_returns tuple 이
         서로 같아 FakeStrategy 의 score_map 키가 충돌(덮어쓰기)한다.
         offset 을 달리 주면 각 피어가 고유한 수익률 시퀀스를 가지므로
         (target_lr_tuple, peer_lr_tuple) 키가 모두 달라 충돌이 없다.
    """
    return [p + offset for p in _BASE_PRICES]


# ---------------------------------------------------------------------------
# 케이스 1: 정상 top_k — 상위 K 개만 반환한다
# ---------------------------------------------------------------------------

class TestFindSimilarTickers_정상_top_k:
    def test_top_k보다_많은_종목이_있으면_상위_K개만_반환한다(self) -> None:
        """WHY: top_k 는 반환 결과의 최대 개수를 제한한다.
        유니버스에 10개 종목이 있고 top_k=3 이면 3개만 나와야 한다.
        """
        tickers = [_TARGET] + [_ticker(f"T{i:02d}") for i in range(10)]
        universe = _make_universe("TEST", tickers, _AS_OF)

        # target 포함 전체 시계열 준비
        series_map = {t: _make_series(t, _BASE_PRICES) for t in tickers}
        repo = FakeRepository(series_map)
        source = FakeUniverseSource(universe)
        strategy = FakeConstantStrategy(constant=0.5)

        query = FindSimilarQuery(
            target=_TARGET,
            universe_name="TEST",
            as_of=_AS_OF,
            top_k=3,
        )
        use_case = FindSimilarTickers(
            repository=repo,
            universe_source=source,
            strategy=strategy,
        )

        results = use_case.execute(query)

        assert len(results) == 3

    def test_반환된_결과에_target_자신은_포함되지_않는다(self) -> None:
        """WHY: 자기 자신과의 유사도는 탐색 결과로 의미가 없다.
        target 이 유니버스에 포함되어 있어도 결과에서 제외돼야 한다.
        """
        tickers = [_TARGET, _PEER_A, _PEER_B]
        universe = _make_universe("TEST", tickers, _AS_OF)

        series_map = {t: _make_series(t, _BASE_PRICES) for t in tickers}
        repo = FakeRepository(series_map)
        source = FakeUniverseSource(universe)
        strategy = FakeConstantStrategy(constant=0.8)

        query = FindSimilarQuery(
            target=_TARGET,
            universe_name="TEST",
            as_of=_AS_OF,
            top_k=10,
        )
        results = FindSimilarTickers(
            repository=repo,
            universe_source=source,
            strategy=strategy,
        ).execute(query)

        result_tickers = [r.ticker for r in results]
        assert _TARGET not in result_tickers


# ---------------------------------------------------------------------------
# 케이스 2: min_abs_score 필터
# ---------------------------------------------------------------------------

class TestFindSimilarTickers_min_score_필터:
    def test_절대값이_min_abs_score_미만인_종목은_제외된다(self) -> None:
        """WHY: min_abs_score 는 노이즈 수준의 낮은 유사도를 걸러낸다.
        |score| < threshold 인 종목은 결과에 포함되지 않아야 한다.
        """
        tickers = [_TARGET, _PEER_A, _PEER_B, _PEER_C]
        universe = _make_universe("TEST", tickers, _AS_OF)

        # WHY: 각 피어마다 다른 offset 을 사용해 고유한 log_returns 를 보장한다.
        #      동일 가격 시계열이면 score_map 키 충돌로 마지막 값만 유효해진다.
        series_map = {
            _TARGET: _make_series(_TARGET, _prices_with_offset(0.0)),
            _PEER_A: _make_series(_PEER_A, _prices_with_offset(5.0)),
            _PEER_B: _make_series(_PEER_B, _prices_with_offset(10.0)),
            _PEER_C: _make_series(_PEER_C, _prices_with_offset(20.0)),
        }
        repo = FakeRepository(series_map)
        source = FakeUniverseSource(universe)

        # target log_returns 를 미리 계산해서 strategy 매핑 구성
        target_lr = [
            lr.value for lr in series_map[_TARGET].log_returns()
        ]
        peer_a_lr = [
            lr.value for lr in series_map[_PEER_A].log_returns()
        ]
        peer_b_lr = [
            lr.value for lr in series_map[_PEER_B].log_returns()
        ]
        peer_c_lr = [
            lr.value for lr in series_map[_PEER_C].log_returns()
        ]

        score_map = {
            (tuple(target_lr), tuple(peer_a_lr)): 0.9,   # 통과
            (tuple(target_lr), tuple(peer_b_lr)): 0.05,  # 필터
            (tuple(target_lr), tuple(peer_c_lr)): -0.8,  # 통과 (절대값 0.8)
        }
        strategy = FakeStrategy(score_map)

        query = FindSimilarQuery(
            target=_TARGET,
            universe_name="TEST",
            as_of=_AS_OF,
            top_k=10,
            min_abs_score=0.1,
        )
        results = FindSimilarTickers(
            repository=repo,
            universe_source=source,
            strategy=strategy,
        ).execute(query)

        result_tickers = [r.ticker for r in results]
        assert _PEER_B not in result_tickers
        assert _PEER_A in result_tickers
        assert _PEER_C in result_tickers
        assert len(results) == 2


# ---------------------------------------------------------------------------
# 케이스 3: target 이 universe 에 없으면 ValueError
# ---------------------------------------------------------------------------

class TestFindSimilarTickers_target_부재_오류:
    def test_target이_유니버스에_없으면_ValueError를_던진다(self) -> None:
        """WHY: 유니버스 범위 밖의 종목으로 유사도 탐색을 수행하면
        데이터 정합성을 보장할 수 없으므로 즉시 오류를 발생시킨다.
        """
        outsider = _ticker("OUTSIDER")
        tickers = [_PEER_A, _PEER_B]
        universe = _make_universe("TEST", tickers, _AS_OF)
        series_map = {t: _make_series(t, _BASE_PRICES) for t in tickers}
        repo = FakeRepository(series_map)
        source = FakeUniverseSource(universe)
        strategy = FakeConstantStrategy()

        query = FindSimilarQuery(
            target=outsider,
            universe_name="TEST",
            as_of=_AS_OF,
        )

        with pytest.raises(ValueError, match="대상 종목이 유니버스에 없습니다"):
            FindSimilarTickers(
                repository=repo,
                universe_source=source,
                strategy=strategy,
            ).execute(query)


# ---------------------------------------------------------------------------
# 케이스 4: 정렬 검증 — |score| 내림차순
# ---------------------------------------------------------------------------

class TestFindSimilarTickers_정렬_검증:
    def test_결과는_절대값_점수_내림차순으로_정렬된다(self) -> None:
        """WHY: 가장 유사한 종목이 앞에 와야 호출자가 상위 N개를 쉽게 사용할 수 있다."""
        tickers = [_TARGET, _PEER_A, _PEER_B, _PEER_C]
        universe = _make_universe("TEST", tickers, _AS_OF)

        # WHY: 피어별 offset 을 달리해 고유한 log_returns tuple 을 보장한다.
        series_map = {
            _TARGET: _make_series(_TARGET, _prices_with_offset(0.0)),
            _PEER_A: _make_series(_PEER_A, _prices_with_offset(5.0)),
            _PEER_B: _make_series(_PEER_B, _prices_with_offset(10.0)),
            _PEER_C: _make_series(_PEER_C, _prices_with_offset(20.0)),
        }
        repo = FakeRepository(series_map)
        source = FakeUniverseSource(universe)

        target_lr = [lr.value for lr in series_map[_TARGET].log_returns()]
        peer_a_lr = [lr.value for lr in series_map[_PEER_A].log_returns()]
        peer_b_lr = [lr.value for lr in series_map[_PEER_B].log_returns()]
        peer_c_lr = [lr.value for lr in series_map[_PEER_C].log_returns()]

        score_map = {
            (tuple(target_lr), tuple(peer_a_lr)): 0.3,
            (tuple(target_lr), tuple(peer_b_lr)): 0.9,
            (tuple(target_lr), tuple(peer_c_lr)): 0.6,
        }
        strategy = FakeStrategy(score_map)

        query = FindSimilarQuery(
            target=_TARGET,
            universe_name="TEST",
            as_of=_AS_OF,
            top_k=10,
        )
        results = FindSimilarTickers(
            repository=repo,
            universe_source=source,
            strategy=strategy,
        ).execute(query)

        scores = [r.score for r in results]
        # 절대값 내림차순 검증
        abs_scores = [abs(s) for s in scores]
        assert abs_scores == sorted(abs_scores, reverse=True)
        # 순서: PEER_B(0.9) > PEER_C(0.6) > PEER_A(0.3)
        assert results[0].ticker == _PEER_B
        assert results[1].ticker == _PEER_C
        assert results[2].ticker == _PEER_A


# ---------------------------------------------------------------------------
# 케이스 5: 절대값 기준 정렬 — 양음 혼재
# ---------------------------------------------------------------------------

class TestFindSimilarTickers_절대값_기준_음수_포함_정렬:
    def test_음수_점수도_절대값으로_정렬된다(self) -> None:
        """WHY: 강한 음의 유사도(-0.9) 는 약한 양의 유사도(0.3) 보다
        절대값이 크므로 더 앞에 위치해야 한다.
        """
        tickers = [_TARGET, _PEER_A, _PEER_B]
        universe = _make_universe("TEST", tickers, _AS_OF)

        # WHY: 피어별 offset 을 달리해 고유한 log_returns tuple 을 보장한다.
        series_map = {
            _TARGET: _make_series(_TARGET, _prices_with_offset(0.0)),
            _PEER_A: _make_series(_PEER_A, _prices_with_offset(5.0)),
            _PEER_B: _make_series(_PEER_B, _prices_with_offset(10.0)),
        }
        repo = FakeRepository(series_map)
        source = FakeUniverseSource(universe)

        target_lr = [lr.value for lr in series_map[_TARGET].log_returns()]
        peer_a_lr = [lr.value for lr in series_map[_PEER_A].log_returns()]
        peer_b_lr = [lr.value for lr in series_map[_PEER_B].log_returns()]

        score_map = {
            (tuple(target_lr), tuple(peer_a_lr)): -0.9,  # 절대값 0.9
            (tuple(target_lr), tuple(peer_b_lr)): 0.3,   # 절대값 0.3
        }
        strategy = FakeStrategy(score_map)

        query = FindSimilarQuery(
            target=_TARGET,
            universe_name="TEST",
            as_of=_AS_OF,
            top_k=10,
        )
        results = FindSimilarTickers(
            repository=repo,
            universe_source=source,
            strategy=strategy,
        ).execute(query)

        # PEER_A(-0.9) 가 PEER_B(0.3) 보다 앞
        assert results[0].ticker == _PEER_A
        assert results[0].score == pytest.approx(-0.9)
        assert results[1].ticker == _PEER_B
        assert results[1].score == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# 케이스 6: 짧은 시리즈 스킵 (N < 2)
# ---------------------------------------------------------------------------

class TestFindSimilarTickers_짧은_시리즈_스킵:
    def test_가격이_1개뿐인_시리즈는_건너뛴다(self) -> None:
        """WHY: 로그수익률 계산에는 최소 2개의 가격이 필요하다.
        1개짜리 시리즈는 로그수익률이 0개이므로 유사도 계산이 불가능하다.
        건너뛰어야 결과 오염 없이 나머지 종목만 반환한다.
        """
        short_ticker = _ticker("SHORT")
        tickers = [_TARGET, _PEER_A, short_ticker]
        universe = _make_universe("TEST", tickers, _AS_OF)

        # SHORT 는 가격 1개 (로그수익률 0개)
        short_series = _make_series(short_ticker, [100.0])

        series_map = {
            _TARGET: _make_series(_TARGET, _BASE_PRICES),
            _PEER_A: _make_series(_PEER_A, _BASE_PRICES),
            short_ticker: short_series,
        }
        repo = FakeRepository(series_map)
        source = FakeUniverseSource(universe)
        strategy = FakeConstantStrategy(constant=0.5)

        query = FindSimilarQuery(
            target=_TARGET,
            universe_name="TEST",
            as_of=_AS_OF,
            top_k=10,
        )
        results = FindSimilarTickers(
            repository=repo,
            universe_source=source,
            strategy=strategy,
        ).execute(query)

        result_tickers = [r.ticker for r in results]
        assert short_ticker not in result_tickers
        assert _PEER_A in result_tickers

    def test_load가_None을_반환하는_종목은_건너뛴다(self) -> None:
        """WHY: 저장소에 데이터가 없는 종목은 건너뛰어야 한다.
        None 을 유사도 계산에 전달하면 예외가 발생하므로 조기에 걸러야 한다.
        """
        missing_ticker = _ticker("MISSING")
        tickers = [_TARGET, _PEER_A, missing_ticker]
        universe = _make_universe("TEST", tickers, _AS_OF)

        # MISSING 은 저장소에 없음
        series_map = {
            _TARGET: _make_series(_TARGET, _BASE_PRICES),
            _PEER_A: _make_series(_PEER_A, _BASE_PRICES),
        }
        repo = FakeRepository(series_map)
        source = FakeUniverseSource(universe)
        strategy = FakeConstantStrategy(constant=0.5)

        query = FindSimilarQuery(
            target=_TARGET,
            universe_name="TEST",
            as_of=_AS_OF,
            top_k=10,
        )
        results = FindSimilarTickers(
            repository=repo,
            universe_source=source,
            strategy=strategy,
        ).execute(query)

        result_tickers = [r.ticker for r in results]
        assert missing_ticker not in result_tickers
        assert _PEER_A in result_tickers


# ---------------------------------------------------------------------------
# 케이스 7: 결정론성 — 동일 입력 → 동일 출력
# ---------------------------------------------------------------------------

class TestFindSimilarTickers_결정론성:
    def test_동일한_query를_두_번_실행하면_동일한_결과를_반환한다(self) -> None:
        """WHY: 유스케이스는 부작용 없는 순수 연산이어야 한다.
        동일 입력에 대해 항상 같은 순서와 점수를 반환해야 한다.
        """
        tickers = [_TARGET, _PEER_A, _PEER_B, _PEER_C]
        universe = _make_universe("TEST", tickers, _AS_OF)

        # WHY: 피어별 offset 을 달리해 고유한 log_returns tuple 을 보장한다.
        series_map = {
            _TARGET: _make_series(_TARGET, _prices_with_offset(0.0)),
            _PEER_A: _make_series(_PEER_A, _prices_with_offset(5.0)),
            _PEER_B: _make_series(_PEER_B, _prices_with_offset(10.0)),
            _PEER_C: _make_series(_PEER_C, _prices_with_offset(20.0)),
        }
        repo = FakeRepository(series_map)
        source = FakeUniverseSource(universe)

        target_lr = [lr.value for lr in series_map[_TARGET].log_returns()]
        peer_a_lr = [lr.value for lr in series_map[_PEER_A].log_returns()]
        peer_b_lr = [lr.value for lr in series_map[_PEER_B].log_returns()]
        peer_c_lr = [lr.value for lr in series_map[_PEER_C].log_returns()]

        score_map = {
            (tuple(target_lr), tuple(peer_a_lr)): 0.7,
            (tuple(target_lr), tuple(peer_b_lr)): 0.4,
            (tuple(target_lr), tuple(peer_c_lr)): 0.85,
        }
        strategy = FakeStrategy(score_map)

        query = FindSimilarQuery(
            target=_TARGET,
            universe_name="TEST",
            as_of=_AS_OF,
            top_k=3,
        )
        use_case = FindSimilarTickers(
            repository=repo,
            universe_source=source,
            strategy=strategy,
        )

        first_run = use_case.execute(query)
        second_run = use_case.execute(query)

        assert len(first_run) == len(second_run)
        for a, b in zip(first_run, second_run):
            assert a.ticker == b.ticker
            assert a.score == pytest.approx(b.score)
