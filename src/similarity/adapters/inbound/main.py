"""
ASGI 애플리케이션 부트스트랩 (인바운드 어댑터).

WHY: docker 환경에서 uvicorn 이 `similarity.adapters.inbound.main:app` 으로
     직접 import 할 수 있는 단일 진입점이 필요하다.
     의존성 구성(DuckDB 경로, 유니버스 시드)은 환경변수로만 제어해
     이미지 재빌드 없이 환경을 전환할 수 있다.

환경변수:
    DUCKDB_PATH   : DuckDB 파일 경로 (기본 /data/sim_money.duckdb)
    SEED_TICKERS  : 쉼표 구분 'MARKET:SYMBOL' 문자열 (기본 KRX:005930,KRX:000660)
"""
from __future__ import annotations

import os
from datetime import date
from typing import Callable

from market_data.adapters.outbound.duckdb_price_repository import DuckDBPriceRepository
from market_data.domain.ticker import Ticker
from similarity.adapters.inbound.fastapi_app import create_app
from similarity.domain.cointegration_strategy import CointegrationStrategy
from similarity.domain.spearman_strategy import SpearmanStrategy
from similarity.domain.weighted_sum_strategy import SimilarityWeights, WeightedSumStrategy
from universe.application.ports import UniverseSource
from universe.domain.universe_snapshot import UniverseSnapshot

# ---------------------------------------------------------------------------
# 환경변수 상수 — 매직 문자열 금지
# ---------------------------------------------------------------------------
_ENV_DUCKDB_PATH = "DUCKDB_PATH"
_ENV_SEED_TICKERS = "SEED_TICKERS"
_DEFAULT_DUCKDB_PATH = "/data/sim_money.duckdb"
_DEFAULT_SEED_TICKERS = "KRX:005930,KRX:000660"

# 유니버스 이름 상수 — M1 플레이스홀더에서 모든 이름에 동일 시드 반환
_PLACEHOLDER_UNIVERSE_NAME = "M1_PLACEHOLDER"


class _InMemoryUniverseSource:
    """M1 플레이스홀더 유니버스 소스.

    WHY: M1 단계에서는 실제 KRX/SP500 API 연동이 없으므로
         환경변수(SEED_TICKERS)로 주입된 종목을 항상 반환한다.
         Phase 2 에서 실제 UniverseSource 구현체로 교체한다.
    """

    def __init__(self, tickers: tuple[Ticker, ...]) -> None:
        self._tickers = tickers

    def fetch(self, name: str, as_of: date) -> UniverseSnapshot:
        """요청된 유니버스 이름에 무관하게 시드 종목 스냅샷을 반환한다."""
        return UniverseSnapshot(
            name=name,
            as_of=as_of,
            tickers=self._tickers,
        )


def _parse_seed_tickers(raw: str) -> tuple[Ticker, ...]:
    """환경변수 문자열을 Ticker tuple 로 변환한다.

    Args:
        raw: 쉼표 구분 'MARKET:SYMBOL' 문자열

    Returns:
        중복 제거된 Ticker tuple
    """
    seen: set[Ticker] = set()
    result: list[Ticker] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        ticker = Ticker.from_string(token)
        if ticker not in seen:
            seen.add(ticker)
            result.append(ticker)
    if not result:
        raise ValueError(f"SEED_TICKERS 에 유효한 종목이 없습니다: {raw!r}")
    return tuple(result)


def _build_strategy_factory() -> Callable[[SimilarityWeights], WeightedSumStrategy]:
    """가중치를 받아 WeightedSumStrategy 를 생성하는 팩토리를 반환한다."""
    return lambda weights: WeightedSumStrategy(weights=weights)


def _build_app():
    """환경변수를 읽어 FastAPI 앱 인스턴스를 생성한다."""
    db_path = os.environ.get(_ENV_DUCKDB_PATH, _DEFAULT_DUCKDB_PATH)
    seed_raw = os.environ.get(_ENV_SEED_TICKERS, _DEFAULT_SEED_TICKERS)

    repository = DuckDBPriceRepository(db_path=db_path)
    seed_tickers = _parse_seed_tickers(seed_raw)
    universe_source: UniverseSource = _InMemoryUniverseSource(seed_tickers)
    strategy_factory = _build_strategy_factory()
    # WHY: 무가중치 전략은 stateless 이므로 앱 수명 동안 단일 인스턴스 재사용.
    strategy_registry = {
        "spearman": SpearmanStrategy(),
        "cointegration": CointegrationStrategy(),
    }

    return create_app(
        repository,
        universe_source,
        strategy_factory,
        strategy_registry=strategy_registry,
    )


# uvicorn 이 직접 참조하는 ASGI app 객체
app = _build_app()
