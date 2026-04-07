"""
market_data 애플리케이션 계층 포트 정의.

WHY: 헥사고날 아키텍처(포트-어댑터 패턴)에서 유스케이스는 외부 인프라(FinanceDataReader,
     DuckDB 등)에 직접 의존하면 안 된다. Protocol 로 포트를 선언함으로써 의존성이
     안쪽(도메인)을 향하도록 역전시키고, 어댑터 구현을 교체하더라도 유스케이스
     로직을 변경하지 않아도 되게 한다. (DIP - 의존성 역전 원칙)
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Protocol

from market_data.domain.price_series import PriceSeries
from market_data.domain.ticker import Ticker


class MarketDataSource(Protocol):
    """외부 시장 데이터 소스 포트.

    WHY: FinanceDataReader, yfinance, 직접 API 호출 등 다양한 구현체를
         동일한 인터페이스로 교체할 수 있도록 Protocol 로 추상화한다.
    """

    def fetch(
        self,
        ticker: Ticker,
        start: date,
        end: date,
    ) -> Optional[PriceSeries]:
        """지정 기간의 수정주가 시계열을 가져온다.

        데이터가 없으면 None 을 반환한다.
        """
        ...


class PriceRepository(Protocol):
    """수정주가 시계열 영속성 포트.

    WHY: DuckDB, PostgreSQL, CSV 등 저장소 구현을 교체할 때
         유스케이스 코드가 영향받지 않도록 포트로 분리한다.
    """

    def save(self, series: PriceSeries) -> None:
        """PriceSeries 를 저장소에 저장한다."""
        ...

    def latest_date(self, ticker: Ticker) -> Optional[date]:
        """저장소에 보유한 해당 종목의 가장 최근 날짜를 반환한다.

        데이터가 없으면 None 을 반환한다.
        """
        ...
