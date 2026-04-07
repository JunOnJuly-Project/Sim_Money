"""
PriceSeries 애그리거트 TDD RED 단계 테스트.

WHY: PriceSeries 는 시계열 유효성(날짜 오름차순, 중복 없음, 최소 1개)을 보장하고
     log_returns / latest_date / is_sufficient 연산의 진입점이 되는 핵심 애그리거트다.
     RED 단계이므로 구현 없이 테스트만 존재한다.
"""
import math
from datetime import date
from decimal import Decimal

import pytest

from market_data.domain.adjusted_price import AdjustedPrice
from market_data.domain.log_return import LogReturn
from market_data.domain.market import Market
from market_data.domain.ticker import Ticker

# 아직 구현이 없으므로 ImportError 가 기대된다.
from market_data.domain.price_series import PriceSeries


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------

def _price(value: float) -> AdjustedPrice:
    """float 로부터 AdjustedPrice 를 빠르게 생성하는 인라인 헬퍼."""
    return AdjustedPrice.from_float(value)


def _ticker() -> Ticker:
    """테스트 전용 기본 Ticker."""
    return Ticker(market=Market.KRX, symbol="005930")


def _make_prices(*pairs: tuple[date, float]) -> tuple[tuple[date, AdjustedPrice], ...]:
    """(date, float) 쌍 목록을 PriceSeries 입력 형식으로 변환한다."""
    return tuple((d, _price(p)) for d, p in pairs)


# ---------------------------------------------------------------------------
# 정상 생성 케이스
# ---------------------------------------------------------------------------

class TestPriceSeries_정상_생성:
    def test_단일_가격으로_생성하면_예외없이_인스턴스가_반환된다(self):
        ticker = _ticker()
        prices = _make_prices((date(2024, 1, 2), 70000.0))
        ps = PriceSeries(ticker=ticker, prices=prices)
        assert ps.ticker == ticker
        assert len(ps.prices) == 1

    def test_오름차순_날짜_세_개로_생성하면_성공한다(self):
        prices = _make_prices(
            (date(2024, 1, 2), 70000.0),
            (date(2024, 1, 3), 71000.0),
            (date(2024, 1, 4), 72000.0),
        )
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        assert len(ps) == 3

    def test_frozen_이므로_prices_직접_수정이_불가능하다(self):
        prices = _make_prices(
            (date(2024, 1, 2), 70000.0),
            (date(2024, 1, 3), 71000.0),
        )
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        with pytest.raises((AttributeError, TypeError)):
            ps.prices = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 불변식 위반 케이스
# ---------------------------------------------------------------------------

class TestPriceSeries_불변식_위반:
    def test_prices_가_비어있으면_ValueError_를_발생시킨다(self):
        with pytest.raises(ValueError):
            PriceSeries(ticker=_ticker(), prices=())

    def test_날짜가_내림차순이면_ValueError_를_발생시킨다(self):
        prices = _make_prices(
            (date(2024, 1, 3), 71000.0),
            (date(2024, 1, 2), 70000.0),
        )
        with pytest.raises(ValueError, match="오름차순"):
            PriceSeries(ticker=_ticker(), prices=prices)

    def test_중복된_날짜가_있으면_ValueError_를_발생시킨다(self):
        prices = _make_prices(
            (date(2024, 1, 2), 70000.0),
            (date(2024, 1, 2), 71000.0),
        )
        with pytest.raises(ValueError, match="중복"):
            PriceSeries(ticker=_ticker(), prices=prices)


# ---------------------------------------------------------------------------
# log_returns 케이스
# ---------------------------------------------------------------------------

class TestPriceSeries_log_returns:
    def test_가격_두_개일_때_log_returns_길이는_1이다(self):
        prices = _make_prices(
            (date(2024, 1, 2), 100.0),
            (date(2024, 1, 3), 110.0),
        )
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        returns = ps.log_returns()
        assert len(returns) == 1

    def test_가격_N_개일_때_log_returns_길이는_N_minus_1_이다(self):
        prices = _make_prices(
            (date(2024, 1, 2), 100.0),
            (date(2024, 1, 3), 105.0),
            (date(2024, 1, 4), 110.0),
            (date(2024, 1, 5), 108.0),
        )
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        assert len(ps.log_returns()) == 3

    def test_log_returns_값이_수학적으로_올바르다(self):
        prices = _make_prices(
            (date(2024, 1, 2), 100.0),
            (date(2024, 1, 3), 110.0),
        )
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        returns = ps.log_returns()
        expected = math.log(110.0 / 100.0)
        assert math.isclose(returns[0].value, expected, rel_tol=1e-9)

    def test_log_returns_반환타입은_LogReturn_튜플이다(self):
        prices = _make_prices(
            (date(2024, 1, 2), 100.0),
            (date(2024, 1, 3), 105.0),
        )
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        returns = ps.log_returns()
        assert isinstance(returns, tuple)
        assert all(isinstance(r, LogReturn) for r in returns)


# ---------------------------------------------------------------------------
# latest_date 케이스
# ---------------------------------------------------------------------------

class TestPriceSeries_latest_date:
    def test_latest_date_는_마지막_날짜를_반환한다(self):
        prices = _make_prices(
            (date(2024, 1, 2), 100.0),
            (date(2024, 1, 3), 105.0),
            (date(2024, 1, 4), 110.0),
        )
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        assert ps.latest_date() == date(2024, 1, 4)

    def test_단일_가격일_때_latest_date_는_그_날짜를_반환한다(self):
        prices = _make_prices((date(2024, 6, 15), 50000.0))
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        assert ps.latest_date() == date(2024, 6, 15)


# ---------------------------------------------------------------------------
# is_sufficient 케이스
# ---------------------------------------------------------------------------

class TestPriceSeries_is_sufficient:
    def test_가격_개수가_252_이상이면_True_를_반환한다(self):
        base = date(2024, 1, 1)
        pairs = tuple(
            (date(2024, 1, 1).replace(day=1) if i == 0
             else date(2020 + i // 365, 1 + (i % 365) // 31, 1 + (i % 31)),
             100.0 + i)
            for i in range(252)
        )
        # 날짜 정렬 보장을 위해 단순 연속 정수 날짜 생성
        from datetime import timedelta
        start = date(2023, 1, 1)
        dates_and_prices = tuple(
            (start + timedelta(days=i), 100.0 + i) for i in range(252)
        )
        ps = PriceSeries(ticker=_ticker(), prices=_make_prices(*dates_and_prices))
        assert ps.is_sufficient() is True

    def test_가격_개수가_252_미만이면_False_를_반환한다(self):
        prices = _make_prices(
            (date(2024, 1, 2), 100.0),
            (date(2024, 1, 3), 105.0),
        )
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        assert ps.is_sufficient() is False

    def test_min_obs_커스텀_값으로_is_sufficient_를_판단한다(self):
        prices = _make_prices(
            (date(2024, 1, 2), 100.0),
            (date(2024, 1, 3), 105.0),
            (date(2024, 1, 4), 110.0),
        )
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        assert ps.is_sufficient(min_obs=3) is True
        assert ps.is_sufficient(min_obs=4) is False


# ---------------------------------------------------------------------------
# __len__ 케이스
# ---------------------------------------------------------------------------

class TestPriceSeries_len:
    def test_len_은_가격_개수를_반환한다(self):
        prices = _make_prices(
            (date(2024, 1, 2), 100.0),
            (date(2024, 1, 3), 105.0),
            (date(2024, 1, 4), 110.0),
        )
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        assert len(ps) == 3

    def test_단일_가격일_때_len_은_1이다(self):
        prices = _make_prices((date(2024, 1, 2), 100.0))
        ps = PriceSeries(ticker=_ticker(), prices=prices)
        assert len(ps) == 1
