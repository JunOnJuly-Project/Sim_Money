"""시장 데이터 시드 스크립트 (M6 Phase 1-3).

WHY: UI/백테스트/리밸런싱 페이지가 실제 데이터로 동작하려면 DuckDB 에
     다종목 일봉 히스토리가 적재되어 있어야 한다. 본 스크립트는
     FinanceDataReaderSource + DuckDBPriceRepository + IngestPrices 를 조립해
     KRX 대형주 + US 대표 종목 2년치를 멱등 적재한다.

사용:
    python scripts/seed_market_data.py [--years 2] [--db data/sim_money.duckdb]

재실행해도 INSERT OR REPLACE 로 중복 없이 최신 값으로 덮어쓴다.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# WHY: 스크립트를 어떤 cwd 에서 실행해도 src/ 패키지를 import 가능하게 한다.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from market_data.adapters.outbound.duckdb_price_repository import DuckDBPriceRepository  # noqa: E402
from market_data.adapters.outbound.finance_data_reader_source import FinanceDataReaderSource  # noqa: E402
from market_data.application.ingest_prices import IngestPrices  # noqa: E402
from market_data.domain.market import Market  # noqa: E402
from market_data.domain.ticker import Ticker  # noqa: E402


# ---------------------------------------------------------------------------
# 시드 유니버스 — 섹터 다양성 + 페어 트레이딩 후보가 풍부하도록 구성
# ---------------------------------------------------------------------------

# KRX 대형주 30선 (IT / 반도체 / 2차전지 / 금융 / 자동차 / 화학 / 바이오 / 엔터)
_KRX_SYMBOLS: tuple[str, ...] = (
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "373220",  # LG에너지솔루션
    "207940",  # 삼성바이오로직스
    "005380",  # 현대차
    "000270",  # 기아
    "005490",  # POSCO홀딩스
    "051910",  # LG화학
    "006400",  # 삼성SDI
    "035420",  # NAVER
    "035720",  # 카카오
    "068270",  # 셀트리온
    "055550",  # 신한지주
    "105560",  # KB금융
    "086790",  # 하나금융지주
    "316140",  # 우리금융지주
    "138040",  # 메리츠금융지주
    "032830",  # 삼성생명
    "015760",  # 한국전력
    "017670",  # SK텔레콤
    "030200",  # KT
    "033780",  # KT&G
    "003550",  # LG
    "009150",  # 삼성전기
    "066570",  # LG전자
    "010130",  # 고려아연
    "011200",  # HMM
    "028260",  # 삼성물산
    "251270",  # 넷마블
    "036570",  # 엔씨소프트
)

# US 대표주 15선 (빅테크 + 반도체 + 소비재 + ETF)
_US_SYMBOLS: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "META",
    "NVDA",
    "TSLA",
    "AMD",
    "NFLX",
    "INTC",
    "KO",
    "JPM",
    "SPY",   # S&P500 ETF
    "QQQ",   # Nasdaq100 ETF
    "IWM",   # Russell2000 ETF
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sim_Money 시장 데이터 시드")
    parser.add_argument(
        "--years",
        type=int,
        default=2,
        help="적재 기간(년). 기본 2년.",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(_PROJECT_ROOT / "data" / "sim_money.duckdb"),
        help="DuckDB 파일 경로.",
    )
    return parser.parse_args()


def _build_tickers() -> tuple[Ticker, ...]:
    """KRX + NASDAQ 시드 유니버스를 Ticker 튜플로 변환한다.

    WHY: US 종목은 시장 구분을 NASDAQ 으로 통일한다. ETF(SPY/IWM) 는 실제로
         NYSE arca 지만 FinanceDataReader 는 심볼만 보고 조회하므로 시장 구분은
         어댑터 조회에 영향이 없다. 본 시드는 탐색/백테스트용 스캐폴드다.
    """
    krx = [Ticker(market=Market.KRX, symbol=s) for s in _KRX_SYMBOLS]
    us = [Ticker(market=Market.NASDAQ, symbol=s) for s in _US_SYMBOLS]
    return tuple(krx + us)


def main() -> int:
    args = _parse_args()
    end = date.today()
    start = end - timedelta(days=365 * args.years)

    tickers = _build_tickers()
    print(f"[seed] tickers={len(tickers)} range={start}→{end} db={args.db}")

    repository = DuckDBPriceRepository(db_path=args.db)
    source = FinanceDataReaderSource()
    ingest = IngestPrices(source=source, repository=repository)

    total_rows = 0
    ok = 0
    fail = 0
    for i, ticker in enumerate(tickers, 1):
        label = f"{ticker.market.value}:{ticker.symbol}"
        try:
            rows = ingest.execute(ticker, start, end)
            total_rows += rows
            ok += 1
            print(f"  [{i:3d}/{len(tickers)}] {label:20s} +{rows} rows")
        except Exception as exc:  # noqa: BLE001 — 시드는 개별 실패 허용
            fail += 1
            print(f"  [{i:3d}/{len(tickers)}] {label:20s} FAIL: {exc}")

    print(f"[seed] done ok={ok} fail={fail} rows={total_rows}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
