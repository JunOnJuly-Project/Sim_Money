"""
FinanceDataReaderSource 아웃바운드 어댑터.

WHY: FinanceDataReader 라이브러리는 실제 네트워크 호출을 수행한다.
     어댑터 계층에서만 라이브러리를 알고 도메인은 순수하게 유지한다.
     생성자 주입(reader=None)으로 테스트 시 FakeReader 로 대체가능하고,
     실운영 시 lazy import 로 불필요한 import 오류를 방지한다.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from market_data.domain.adjusted_price import AdjustedPrice
from market_data.domain.price_series import PriceSeries
from market_data.domain.ticker import Ticker

# 컬럼명 상수 — 매직 스트링 금지
_COL_ADJ_CLOSE = "Adj Close"
_COL_CLOSE = "Close"


class FinanceDataReaderSource:
    """FinanceDataReader 를 감싸는 아웃바운드 어댑터.

    WHY: 포트(PriceDataSource) 계약을 이행하면서 외부 라이브러리 의존성을
         이 클래스 내부로 격리한다. 도메인 레이어는 이 클래스를 알지 못한다.
    """

    def __init__(self, reader: Any = None) -> None:
        """reader 가 None 이면 FinanceDataReader 를 lazy import 해서 사용한다.

        WHY lazy import: 테스트 환경에서 FakeReader 를 주입하면 실제 라이브러리를
        import 하지 않아도 되므로 테스트 격리가 보장된다.
        """
        if reader is None:
            import FinanceDataReader as fdr  # noqa: PLC0415
            self._reader = fdr
        else:
            self._reader = reader

    def fetch(
        self,
        ticker: Ticker,
        start: date,
        end: date,
    ) -> PriceSeries | None:
        """종목의 수정주가 시계열을 조회한다.

        WHY: 'Adj Close' 를 우선 사용하는 이유는 배당·액면분할이 반영된
             수정주가가 수익률 계산의 정확도를 높이기 때문이다(ADR-002).
             빈 DataFrame 이면 None 을 반환해 호출자가 '데이터 없음'을
             명시적으로 처리할 수 있게 한다.
        """
        df = self._reader.DataReader(ticker.symbol, start, end)

        if df.empty:
            return None

        price_column = _COL_ADJ_CLOSE if _COL_ADJ_CLOSE in df.columns else _COL_CLOSE
        return self._build_price_series(ticker, df, price_column)

    def _build_price_series(
        self,
        ticker: Ticker,
        df: Any,
        price_column: str,
    ) -> PriceSeries:
        """DataFrame 에서 (date, AdjustedPrice) 튜플 시퀀스를 생성한다.

        WHY: DatetimeIndex 를 date 로 변환하는 책임을 이 메서드에 집중시켜
             fetch 함수를 20줄 이내로 유지한다.
        """
        prices = tuple(
            (idx.date(), AdjustedPrice.from_float(float(row[price_column])))
            for idx, row in df.iterrows()
        )
        return PriceSeries(ticker=ticker, prices=prices)
