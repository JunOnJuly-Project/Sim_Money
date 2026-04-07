"""
DuckDB 기반 수정주가 시계열 레포지터리 어댑터.

WHY: PriceRepository 포트의 DuckDB 구현체다.
     인메모리(':memory:') 및 파일 경로 모두 지원해
     테스트에서는 디스크를 건드리지 않고 검증할 수 있다.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import duckdb

from market_data.domain.adjusted_price import AdjustedPrice
from market_data.domain.price_series import PriceSeries
from market_data.domain.ticker import Ticker

# ---------------------------------------------------------------------------
# SQL 상수 — 매직 문자열을 모듈 상수로 격리
# WHY: SQL 을 상수로 분리하면 변경 시 한 곳만 수정하고
#      실수로 인한 SQL 인젝션·오타를 줄인다.
# ---------------------------------------------------------------------------

_SCHEMA_SQL: str = """
CREATE TABLE IF NOT EXISTS prices (
    market     VARCHAR   NOT NULL,
    symbol     VARCHAR   NOT NULL,
    trade_date DATE      NOT NULL,
    adj_close  DOUBLE    NOT NULL,
    PRIMARY KEY (market, symbol, trade_date)
)
"""

_INSERT_SQL: str = """
INSERT OR REPLACE INTO prices (market, symbol, trade_date, adj_close)
VALUES (?, ?, ?, ?)
"""

_LATEST_DATE_SQL: str = """
SELECT MAX(trade_date)
FROM prices
WHERE market = ? AND symbol = ?
"""

_LOAD_SQL: str = """
SELECT trade_date, adj_close
FROM prices
WHERE market = ? AND symbol = ?
ORDER BY trade_date ASC
"""


class DuckDBPriceRepository:
    """수정주가 시계열을 DuckDB 에 저장·조회하는 아웃바운드 어댑터.

    WHY: DuckDB 는 로컬 OLAP 엔진으로 컬럼형 저장 덕에
         날짜 범위 조회와 집계가 빠르고 외부 서버 의존이 없다.
    """

    def __init__(self, db_path: str) -> None:
        """DuckDB 연결을 초기화하고 스키마를 보장한다.

        Args:
            db_path: DB 파일 경로 또는 ':memory:' (인메모리).
        """
        self._con = duckdb.connect(str(db_path))
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """prices 테이블이 없으면 생성한다.

        WHY: IF NOT EXISTS 로 멱등하게 처리해
             초기화 코드를 중복 실행해도 오류가 발생하지 않는다.
        """
        self._con.execute(_SCHEMA_SQL)

    def save(self, series: PriceSeries) -> None:
        """PriceSeries 의 모든 (날짜, 수정주가) 를 저장한다.

        WHY: INSERT OR REPLACE 를 사용해 동일 PK(market, symbol, trade_date) 가
             이미 존재해도 오류 없이 최신 값으로 교체한다.
             이로써 데이터 수집 파이프라인을 재실행해도 중복 row 가 생기지 않는다.
        """
        market_val = series.ticker.market.value
        symbol_val = series.ticker.symbol

        rows = [
            (market_val, symbol_val, trade_date, float(adj_close.value))
            for trade_date, adj_close in series.prices
        ]
        self._con.executemany(_INSERT_SQL, rows)

    def latest_date(self, ticker: Ticker) -> Optional[date]:
        """저장된 해당 종목의 가장 최근 trade_date 를 반환한다.

        WHY: MAX(trade_date) 는 증분 수집 시 마지막 수집일을 파악하는
             가장 단순하고 정확한 방법이다.
             데이터가 없으면 MAX 결과가 NULL 이므로 명시적으로 None 을 반환한다.
        """
        row = self._con.execute(
            _LATEST_DATE_SQL,
            [ticker.market.value, ticker.symbol],
        ).fetchone()

        if row is None or row[0] is None:
            return None
        return row[0]

    def load(self, ticker: Ticker) -> Optional[PriceSeries]:
        """저장된 종목의 수정주가 시계열 전체를 PriceSeries 로 반환한다.

        WHY: 유사도 계산 등 하위 서비스가 DB 에서 시계열을 안전하게 재구성할 수 있도록
             도메인 객체 형태로 반환한다. 데이터가 없으면 None 을 반환해
             호출자가 '이력 없음' 상태를 명시적으로 처리하게 한다.
        """
        rows = self._con.execute(
            _LOAD_SQL,
            [ticker.market.value, ticker.symbol],
        ).fetchall()

        if not rows:
            return None

        prices = tuple(
            (trade_date, AdjustedPrice.from_float(adj_close))
            for trade_date, adj_close in rows
        )
        return PriceSeries(ticker=ticker, prices=prices)

    def close(self) -> None:
        """DuckDB 연결을 닫아 리소스를 반환한다.

        WHY: 테스트 픽스처나 컨텍스트 매니저에서 명시적으로 호출해
             연결 누수를 방지한다.
        """
        self._con.close()
