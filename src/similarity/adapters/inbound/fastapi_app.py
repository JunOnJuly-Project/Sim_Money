"""
유사 종목 탐색 FastAPI 인바운드 어댑터.

WHY: 헥사고날 아키텍처에서 HTTP 관심사(라우팅·직렬화·에러 변환)와
     도메인 로직을 분리한다. 이 파일은 오직 FindSimilarTickers 포트에만
     의존하므로 인프라 교체(Flask, gRPC 등) 시 도메인 코드를 건드리지 않아도 된다.
"""
from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException, Query

from market_data.domain.market import Market
from market_data.domain.ticker import Ticker
from similarity.application.find_similar_tickers import FindSimilarQuery, FindSimilarTickers

# 에러 메시지 식별자 — 매직 문자열 금지
ERR_NOT_IN_UNIVERSE = "유니버스에 없습니다"

# 기본 top_k 값
_DEFAULT_TOP_K = 10
# 기본 최소 절대 점수
_DEFAULT_MIN_ABS_SCORE = 0.0


def create_app(find_similar: FindSimilarTickers) -> FastAPI:
    """FastAPI 앱 인스턴스를 생성하고 라우트를 등록한다.

    WHY: 앱 팩토리 패턴으로 find_similar 를 클로저에 캡처해
         테스트마다 독립적인 Fake 인스턴스를 주입할 수 있도록 한다.
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
    ) -> dict:
        """유사 종목 목록을 반환한다."""
        target = Ticker(market=Market(market.upper()), symbol=symbol)
        query = FindSimilarQuery(
            target=target,
            universe_name=universe,
            as_of=as_of,
            top_k=top_k,
            min_abs_score=min_abs_score,
        )
        return _execute_query(find_similar, query, target)

    return app


def _execute_query(
    find_similar: FindSimilarTickers,
    query: FindSimilarQuery,
    target: Ticker,
) -> dict:
    """유스케이스를 실행하고 HTTP 에러로 변환한다.

    WHY: ValueError 를 HTTP 상태 코드로 매핑하는 책임을 분리해
         엔드포인트 함수의 가독성을 유지한다.
    """
    try:
        results = find_similar.execute(query)
    except ValueError as exc:
        _raise_http_error(exc)

    return {
        "target": str(target),
        "results": [{"ticker": str(r.ticker), "score": r.score} for r in results],
    }


def _raise_http_error(exc: ValueError) -> None:
    """ValueError 메시지에 따라 적절한 HTTPException 을 발생시킨다.

    WHY: 유니버스 부재는 클라이언트가 요청한 리소스가 없는 상황이므로 404,
         그 외 ValueError 는 잘못된 입력(400) 으로 구분한다.
    """
    if ERR_NOT_IN_UNIVERSE in str(exc):
        raise HTTPException(status_code=404, detail=str(exc))
    raise HTTPException(status_code=400, detail=str(exc))
