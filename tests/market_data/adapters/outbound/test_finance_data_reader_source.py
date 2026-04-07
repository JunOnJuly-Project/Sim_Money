"""
FinanceDataReaderSource 어댑터 TDD RED 단계 테스트.

WHY: FinanceDataReaderSource 는 외부 라이브러리(FinanceDataReader)를 감싸는
     아웃바운드 어댑터다. 실제 네트워크 호출 없이 결정론적으로 동작을 검증하기
     위해 생성자에 FakeReader 를 주입한다. 이 파일은 RED 단계 — 어댑터 구현이
     없으므로 ImportError 가 기대된다.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

# RED: 아래 임포트는 아직 구현이 없으므로 ImportError 가 발생해야 한다.
from market_data.adapters.outbound.finance_data_reader_source import (
    FinanceDataReaderSource,
)
from market_data.domain.market import Market
from market_data.domain.price_series import PriceSeries
from market_data.domain.ticker import Ticker


# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------

def _krx_ticker(symbol: str = "005930") -> Ticker:
    """KRX 종목 Ticker 생성 헬퍼."""
    return Ticker(market=Market.KRX, symbol=symbol)


def _nasdaq_ticker(symbol: str = "AAPL") -> Ticker:
    """NASDAQ 종목 Ticker 생성 헬퍼."""
    return Ticker(market=Market.NASDAQ, symbol=symbol)


def _make_close_df(prices: list[float], start: date) -> pd.DataFrame:
    """'Close' 컬럼만 있는 결정론적 DataFrame 을 생성하는 헬퍼.

    WHY: 각 테스트가 DataFrame 구성 세부사항을 반복하지 않도록 추출한다.
    """
    dates = pd.date_range(start=start, periods=len(prices), freq="B")
    return pd.DataFrame({"Close": prices}, index=dates)


def _make_adj_close_df(
    adj_prices: list[float],
    close_prices: list[float],
    start: date,
) -> pd.DataFrame:
    """'Adj Close' 와 'Close' 두 컬럼이 있는 DataFrame 을 생성하는 헬퍼.

    WHY: 'Adj Close' 우선 사용 케이스를 검증하기 위해 두 컬럼 모두 포함한다.
    """
    dates = pd.date_range(start=start, periods=len(adj_prices), freq="B")
    return pd.DataFrame(
        {"Adj Close": adj_prices, "Close": close_prices},
        index=dates,
    )


# ---------------------------------------------------------------------------
# FakeReader: FinanceDataReader 모듈 호환 테스트 더블
# ---------------------------------------------------------------------------

class FakeReader:
    """FinanceDataReader.DataReader 를 흉내 내는 결정론적 테스트 더블.

    WHY: 실제 FDR 은 네트워크 호출을 수행한다. FakeReader 를 주입하면
         네트워크 없이 DataReader 의 반환 DataFrame 을 완전히 제어할 수 있다.
    """

    def __init__(self, return_df: pd.DataFrame) -> None:
        """반환할 DataFrame 과 호출 기록 초기화."""
        self._return_df = return_df
        # DataReader(symbol, start, end) 호출 인자 기록
        self.calls: list[tuple[str, Any, Any]] = []

    def DataReader(self, symbol: str, start: Any, end: Any) -> pd.DataFrame:
        """호출 인자를 기록하고 사전 주입된 DataFrame 을 반환한다."""
        self.calls.append((symbol, start, end))
        return self._return_df


# ---------------------------------------------------------------------------
# 케이스 1: KRX 종목 정상 fetch
# ---------------------------------------------------------------------------

class TestFinanceDataReaderSource_KRX_정상_fetch:
    def test_KRX_종목_fetch시_PriceSeries를_반환한다(self):
        """WHY: KRX 종목은 symbol 을 그대로 DataReader 에 전달해야 하고,
        결과 PriceSeries 의 ticker 와 가격 개수가 입력과 일치해야 한다.
        """
        ticker = _krx_ticker("005930")
        start = date(2024, 1, 2)
        end = date(2024, 1, 5)
        close_prices = [70_000.0, 70_500.0, 71_000.0]

        fake_df = _make_close_df(close_prices, start)
        fake_reader = FakeReader(return_df=fake_df)

        source = FinanceDataReaderSource(reader=fake_reader)
        result = source.fetch(ticker=ticker, start=start, end=end)

        assert result is not None
        assert isinstance(result, PriceSeries)
        assert result.ticker == ticker
        assert len(result) == len(close_prices)


# ---------------------------------------------------------------------------
# 케이스 2: NASDAQ 종목 정상 fetch
# ---------------------------------------------------------------------------

class TestFinanceDataReaderSource_NASDAQ_정상_fetch:
    def test_NASDAQ_종목_fetch시_PriceSeries를_반환한다(self):
        """WHY: NASDAQ 종목도 symbol 을 그대로 DataReader 에 전달해야 하고,
        반환된 PriceSeries 의 ticker 와 길이가 기대값과 일치해야 한다.
        """
        ticker = _nasdaq_ticker("AAPL")
        start = date(2024, 1, 2)
        end = date(2024, 1, 5)
        close_prices = [185.2, 186.0, 187.5]

        fake_df = _make_close_df(close_prices, start)
        fake_reader = FakeReader(return_df=fake_df)

        source = FinanceDataReaderSource(reader=fake_reader)
        result = source.fetch(ticker=ticker, start=start, end=end)

        assert result is not None
        assert isinstance(result, PriceSeries)
        assert result.ticker == ticker
        assert len(result) == len(close_prices)


# ---------------------------------------------------------------------------
# 케이스 3: 빈 DataFrame → None 반환
# ---------------------------------------------------------------------------

class TestFinanceDataReaderSource_빈_DataFrame:
    def test_빈_DataFrame이면_None을_반환한다(self):
        """WHY: 조회 기간에 거래 데이터가 없으면 None 을 반환해
        호출자가 '데이터 없음' 상태를 명시적으로 처리할 수 있어야 한다.
        """
        ticker = _krx_ticker("005930")
        start = date(2024, 1, 2)
        end = date(2024, 1, 5)

        empty_df = pd.DataFrame(columns=["Close"])
        fake_reader = FakeReader(return_df=empty_df)

        source = FinanceDataReaderSource(reader=fake_reader)
        result = source.fetch(ticker=ticker, start=start, end=end)

        assert result is None


# ---------------------------------------------------------------------------
# 케이스 4: 'Adj Close' 컬럼 우선 사용
# ---------------------------------------------------------------------------

class TestFinanceDataReaderSource_AdjClose_우선:
    def test_Adj_Close_컬럼이_있으면_Close_대신_사용한다(self):
        """WHY: 'Adj Close' 는 배당·액면분할이 반영된 수정주가이므로
        'Close' 보다 우선해서 사용해야 정확한 수익률 계산이 가능하다.
        두 컬럼 값이 다를 때 'Adj Close' 기준으로 PriceSeries 가 생성돼야 한다.
        """
        ticker = _nasdaq_ticker("AAPL")
        start = date(2024, 1, 2)
        end = date(2024, 1, 5)

        # Adj Close 와 Close 값을 의도적으로 다르게 설정
        adj_prices = [180.0, 181.0, 182.0]
        close_prices = [200.0, 201.0, 202.0]

        fake_df = _make_adj_close_df(adj_prices, close_prices, start)
        fake_reader = FakeReader(return_df=fake_df)

        source = FinanceDataReaderSource(reader=fake_reader)
        result = source.fetch(ticker=ticker, start=start, end=end)

        assert result is not None
        # 첫 번째 가격이 Adj Close 기준값이어야 한다
        first_price_value = float(result.prices[0][1].value)
        assert first_price_value == pytest.approx(adj_prices[0])


# ---------------------------------------------------------------------------
# 케이스 5: 'Adj Close' 없으면 'Close' 폴백
# ---------------------------------------------------------------------------

class TestFinanceDataReaderSource_Close_폴백:
    def test_Adj_Close_없으면_Close_컬럼을_사용한다(self):
        """WHY: 일부 시장/기간 데이터에는 'Adj Close' 가 없을 수 있다.
        이때 'Close' 를 폴백으로 사용해 데이터 손실을 방지해야 한다.
        """
        ticker = _krx_ticker("005930")
        start = date(2024, 1, 2)
        end = date(2024, 1, 5)
        close_prices = [70_000.0, 70_500.0, 71_000.0]

        # 'Close' 컬럼만 있는 DataFrame (Adj Close 없음)
        fake_df = _make_close_df(close_prices, start)
        assert "Adj Close" not in fake_df.columns

        fake_reader = FakeReader(return_df=fake_df)

        source = FinanceDataReaderSource(reader=fake_reader)
        result = source.fetch(ticker=ticker, start=start, end=end)

        assert result is not None
        # 첫 번째 가격이 Close 기준값이어야 한다
        first_price_value = float(result.prices[0][1].value)
        assert first_price_value == pytest.approx(close_prices[0])


# ---------------------------------------------------------------------------
# 케이스 6: DataReader 호출 인자 검증
# ---------------------------------------------------------------------------

class TestFinanceDataReaderSource_호출_인자_검증:
    def test_DataReader가_정확한_symbol_start_end로_호출된다(self):
        """WHY: 어댑터가 ticker.symbol, start, end 를 변형 없이
        DataReader 에 그대로 전달해야 포트 계약이 정확히 이행된다.
        잘못된 인자 전달은 잘못된 데이터 수신으로 이어지므로 명시적으로 검증한다.
        """
        ticker = _krx_ticker("005930")
        start = date(2024, 1, 2)
        end = date(2024, 6, 30)
        close_prices = [70_000.0, 70_500.0]

        fake_df = _make_close_df(close_prices, start)
        fake_reader = FakeReader(return_df=fake_df)

        source = FinanceDataReaderSource(reader=fake_reader)
        source.fetch(ticker=ticker, start=start, end=end)

        assert len(fake_reader.calls) == 1
        called_symbol, called_start, called_end = fake_reader.calls[0]

        # symbol 은 ticker.symbol 과 동일해야 한다
        assert called_symbol == ticker.symbol
        # start / end 는 변형 없이 그대로 전달돼야 한다
        assert called_start == start
        assert called_end == end
