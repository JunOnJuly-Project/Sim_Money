"""
유사 종목 탐색 FastAPI 인바운드 어댑터.

WHY: 헥사고날 아키텍처에서 HTTP 관심사(라우팅·직렬화·에러 변환)와
     도메인 로직을 분리한다. 이 파일은 포트에만 의존하므로
     인프라 교체(Flask, gRPC 등) 시 도메인 코드를 건드리지 않아도 된다.
     strategy_factory 를 주입받아 요청마다 가중치 기반 전략을 동적으로 생성한다.
"""
from __future__ import annotations

from datetime import date
from typing import Callable

from fastapi import FastAPI, HTTPException, Query

from market_data.application.ports import PriceRepository
from market_data.domain.market import Market
from market_data.domain.ticker import Ticker
from similarity.application.find_similar_tickers import FindSimilarQuery, FindSimilarTickers
from similarity.application.ports import SimilarityStrategy
from similarity.domain.weighted_sum_strategy import SimilarityWeights
from universe.application.ports import UniverseSource

# 에러 메시지 식별자 — 매직 문자열 금지
_ERR_NOT_IN_UNIVERSE = "유니버스에 없습니다"
# WHY: 시계열 부재는 아직 데이터가 없는 상태이므로 빈 results 로 처리해
#      클라이언트가 404/400 없이 빈 목록을 수신할 수 있도록 한다.
_ERR_SERIES_MISSING = "시계열 없음"

# 쿼리 파라미터 기본값 상수
_DEFAULT_TOP_K = 10
_DEFAULT_MIN_ABS_SCORE = 0.0
_DEFAULT_W1 = 0.5
_DEFAULT_W2 = 0.3
_DEFAULT_W3 = 0.2


def create_app(
    repository: PriceRepository,
    universe_source: UniverseSource,
    strategy_factory: Callable[[SimilarityWeights], SimilarityStrategy],
) -> FastAPI:
    """FastAPI 앱 인스턴스를 생성하고 라우트를 등록한다.

    WHY: 앱 팩토리 패턴으로 의존성을 클로저에 캡처해
         테스트마다 독립적인 Fake 인스턴스를 주입할 수 있도록 한다.
         strategy_factory 는 요청별로 가중치를 받아 전략을 동적으로 생성한다.

    Args:
        repository: 가격 시계열 저장소 포트
        universe_source: 유니버스 스냅샷 조회 포트
        strategy_factory: SimilarityWeights 를 받아 SimilarityStrategy 를 반환하는 팩토리
    """
    app = FastAPI()

    @app.get("/health")
    def health() -> dict:
        """로드밸런서 헬스 프로브용 엔드포인트."""
        return {"status": "ok"}

    @app.get("/similar/{symbol}")
    def find_similar_endpoint(
        symbol: str,
        market: str = Query(...),
        universe: str = Query(...),
        as_of: date = Query(...),
        top_k: int = Query(_DEFAULT_TOP_K),
        min_abs_score: float = Query(_DEFAULT_MIN_ABS_SCORE),
        w1: float = Query(_DEFAULT_W1),
        w2: float = Query(_DEFAULT_W2),
        w3: float = Query(_DEFAULT_W3),
    ) -> dict:
        """유사 종목 목록을 반환한다."""
        try:
            weights = SimilarityWeights(w1, w2, w3)
            strategy = strategy_factory(weights)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        find_similar = FindSimilarTickers(
            repository=repository,
            universe_source=universe_source,
            strategy=strategy,
        )
        target = Ticker(market=Market(market.upper()), symbol=symbol)
        query = FindSimilarQuery(
            target=target,
            universe_name=universe,
            as_of=as_of,
            top_k=top_k,
            min_abs_score=min_abs_score,
        )
        return _execute_query(find_similar, query, target, weights)

    return app


def _execute_query(
    find_similar: FindSimilarTickers,
    query: FindSimilarQuery,
    target: Ticker,
    weights: SimilarityWeights,
) -> dict:
    """유스케이스를 실행하고 HTTP 에러로 변환한다.

    WHY: ValueError 를 HTTP 상태 코드로 매핑하는 책임을 분리해
         엔드포인트 함수의 가독성을 유지한다.

    Args:
        find_similar: 유사 종목 탐색 유스케이스 인스턴스
        query: 탐색 쿼리 값 객체
        target: 대상 종목 티커
        weights: 응답에 포함할 가중치 값 객체
    """
    try:
        results = find_similar.execute(query)
    except ValueError as exc:
        if _ERR_SERIES_MISSING in str(exc):
            # WHY: 시계열 데이터가 없으면 비교 대상이 없어 빈 결과를 반환한다.
            #      데이터 부재는 클라이언트 오류가 아니라 데이터 미수집 상태이다.
            results = []
        else:
            _raise_http_error(exc)

    return {
        "target": str(target),
        "weights": {"w1": weights.w1, "w2": weights.w2, "w3": weights.w3},
        "results": [{"ticker": str(r.ticker), "score": r.score} for r in results],
    }


def _raise_http_error(exc: ValueError) -> None:
    """ValueError 메시지에 따라 적절한 HTTPException 을 발생시킨다.

    WHY: 유니버스 부재는 클라이언트가 요청한 리소스가 없는 상황이므로 404,
         그 외 ValueError 는 잘못된 입력(400) 으로 구분한다.
    """
    if _ERR_NOT_IN_UNIVERSE in str(exc):
        raise HTTPException(status_code=404, detail=str(exc))
    raise HTTPException(status_code=400, detail=str(exc))
