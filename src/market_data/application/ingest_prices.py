"""
IngestPrices 유스케이스.

WHY: 가격 적재 로직을 단일 유스케이스 클래스에 집중시켜 SRP 를 지키고,
     포트 인터페이스(MarketDataSource, PriceRepository)에만 의존해
     인프라 교체 시 이 파일을 수정하지 않아도 되도록 설계한다. (DIP)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from market_data.application.ports import MarketDataSource, PriceRepository
from market_data.domain.price_series import PriceSeries
from market_data.domain.ticker import Ticker

# 증분 적재 오프셋 — 마지막 보유일 다음 날부터 fetch 해야 중복을 막는다
_NEXT_DAY_OFFSET: int = 1

# 이미 최신 상태임을 나타내는 반환값 (fetch/save 불필요)
_NO_NEW_ROWS: int = 0


@dataclass(frozen=True)
class IngestPrices:
    """가격 시계열 적재 유스케이스.

    WHY: frozen dataclass 로 선언해 생성 후 소스·저장소 의존성이
         변경되는 실수를 컴파일 타임에 차단한다.
         생성자 주입으로 Fake/Mock 교체가 가능해 테스트 격리성을 보장한다.
    """

    source: MarketDataSource
    repository: PriceRepository

    def execute(self, ticker: Ticker, start: date, end: date) -> int:
        """가격 시계열을 적재하고 저장된 행 수를 반환한다.

        WHY: 이미 최신 데이터를 보유한 경우 불필요한 네트워크 호출을 막기 위해
             latest_date 를 먼저 확인하고, 증분 시작일을 계산한다.
        """
        fetch_start = self._resolve_fetch_start(ticker, start, end)
        if fetch_start is None:
            return _NO_NEW_ROWS

        series = self.source.fetch(ticker, fetch_start, end)
        if series is None:
            return _NO_NEW_ROWS

        self.repository.save(series)
        return len(series)

    def _resolve_fetch_start(
        self, ticker: Ticker, requested_start: date, end: date
    ) -> Optional[date]:
        """fetch 시작일을 결정한다.

        WHY: 이미 end 이상의 데이터가 있으면 None 을 반환해 호출자가
             fetch 를 건너뛰도록 신호를 보낸다.
             latest_date 가 있으면 그 다음 날부터 증분 적재한다.
        """
        latest = self.repository.latest_date(ticker)
        if latest is None:
            return requested_start

        # latest_date 가 end 이상이면 이미 최신 상태
        # WHY: 이 조건을 execute 에서 분리해 단일 목적 함수를 유지한다
        return None if self._is_up_to_date(latest, end) else latest + timedelta(days=_NEXT_DAY_OFFSET)

    @staticmethod
    def _is_up_to_date(latest: date, end: date) -> bool:
        """최신 날짜가 end 이상이면 적재가 불필요하다.

        WHY: execute 의 반환 기준을 명시적 불리언으로 표현해 가독성을 높인다.
        """
        return latest >= end
