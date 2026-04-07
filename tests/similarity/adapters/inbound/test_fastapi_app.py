"""
FastAPI 인바운드 어댑터 TDD RED 단계 테스트.

WHY: 헥사고날 아키텍처에서 인바운드 어댑터는 유스케이스 포트에만 의존해야 한다.
     Fake FindSimilarTickers 를 주입해 HTTP 계층(라우팅·직렬화·에러 변환)만
     외부 인프라 없이 결정론적으로 검증한다.

     이 파일은 RED 단계 — fastapi_app 구현이 없으므로
     ImportError 가 기대된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

# RED: 아래 임포트는 아직 구현이 없으므로 ImportError 가 발생해야 한다.
from similarity.adapters.inbound.fastapi_app import create_app
from similarity.application.find_similar_tickers import (
    FindSimilarQuery,
    FindSimilarTickers,
    SimilarityResult,
)
from market_data.domain.market import Market
from market_data.domain.ticker import Ticker


# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------

def _ticker(market_str: str, symbol: str) -> Ticker:
    """테스트 전용 Ticker 생성 헬퍼."""
    return Ticker(market=Market(market_str), symbol=symbol)


# ---------------------------------------------------------------------------
# Fake 유스케이스
# ---------------------------------------------------------------------------

@dataclass
class FakeFindSimilarTickers:
    """FindSimilarTickers 유스케이스의 테스트 더블.

    WHY: 실제 유스케이스 로직(저장소·유니버스·전략)을 배제하고
         HTTP 어댑터 계층만 격리해서 검증한다.
         호출된 쿼리를 기록해 파라미터 전달 여부를 검증할 수 있다.
    """

    fixed_results: list[SimilarityResult] = field(default_factory=list)
    raise_value_error: str | None = None
    recorded_queries: list[FindSimilarQuery] = field(default_factory=list)

    def execute(self, query: FindSimilarQuery) -> list[SimilarityResult]:
        """쿼리를 기록하고 설정된 결과 또는 예외를 반환한다."""
        self.recorded_queries.append(query)
        if self.raise_value_error is not None:
            raise ValueError(self.raise_value_error)
        return self.fixed_results


# ---------------------------------------------------------------------------
# 케이스 1: GET /health → 200, status ok
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_헬스체크_요청하면_200과_status_ok를_반환한다(self) -> None:
        """WHY: /health 엔드포인트는 인프라 의존성 없이
        항상 정상 응답을 반환해 로드밸런서 헬스 프로브에 응답해야 한다.
        """
        fake = FakeFindSimilarTickers()
        app = create_app(find_similar=fake)
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# 케이스 2: GET /similar/{symbol}?... → 200, JSON 구조 검증
# ---------------------------------------------------------------------------

class TestSimilarEndpoint_정상_응답:
    def test_유효한_요청에_200과_올바른_JSON_구조를_반환한다(self) -> None:
        """WHY: 응답 JSON 구조(target 키, results 배열, ticker/score 필드)가
        API 계약에 맞게 직렬화됐는지 검증한다.
        """
        hynix = _ticker("KRX", "000660")
        samsung = _ticker("KRX", "005930")

        fake = FakeFindSimilarTickers(
            fixed_results=[
                SimilarityResult(ticker=hynix, score=0.87),
            ]
        )
        app = create_app(find_similar=fake)
        client = TestClient(app)

        response = client.get(
            "/similar/005930",
            params={
                "market": "KRX",
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
                "top_k": 5,
                "min_abs_score": 0.0,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["target"] == "KRX:005930"
        assert isinstance(body["results"], list)
        assert len(body["results"]) == 1
        first = body["results"][0]
        assert first["ticker"] == "KRX:000660"
        assert "score" in first

    # ---------------------------------------------------------------------------
    # 케이스 3: score 가 JSON 에 float 으로 직렬화된다
    # ---------------------------------------------------------------------------

    def test_score가_JSON에_float으로_직렬화된다(self) -> None:
        """WHY: score 는 수치 계산 결과이므로 JSON 에서 반드시 number(float) 타입이어야 한다.
        문자열이나 null 로 직렬화되면 클라이언트가 정렬·필터를 수행할 수 없다.
        """
        peer = _ticker("KRX", "000660")
        fake = FakeFindSimilarTickers(
            fixed_results=[
                SimilarityResult(ticker=peer, score=0.87),
            ]
        )
        app = create_app(find_similar=fake)
        client = TestClient(app)

        response = client.get(
            "/similar/005930",
            params={
                "market": "KRX",
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
            },
        )

        assert response.status_code == 200
        score_value = response.json()["results"][0]["score"]
        assert isinstance(score_value, float)
        assert score_value == pytest.approx(0.87)

    # ---------------------------------------------------------------------------
    # 케이스 4: top_k 파라미터가 FindSimilarQuery 에 전달됐는지 검증
    # ---------------------------------------------------------------------------

    def test_top_k_파라미터가_유스케이스_쿼리에_전달된다(self) -> None:
        """WHY: HTTP 어댑터는 쿼리 파라미터를 누락 없이 유스케이스 쿼리 객체로
        변환해야 한다. top_k 가 누락되면 유스케이스가 잘못된 개수를 반환한다.
        """
        fake = FakeFindSimilarTickers(fixed_results=[])
        app = create_app(find_similar=fake)
        client = TestClient(app)

        client.get(
            "/similar/005930",
            params={
                "market": "KRX",
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
                "top_k": 7,
            },
        )

        assert len(fake.recorded_queries) == 1
        assert fake.recorded_queries[0].top_k == 7


# ---------------------------------------------------------------------------
# 케이스 5: market 쿼리 파라미터 누락 → 422
# ---------------------------------------------------------------------------

class TestSimilarEndpoint_파라미터_검증:
    def test_market_파라미터_누락시_422를_반환한다(self) -> None:
        """WHY: market 은 Ticker 생성에 필수적인 파라미터이므로
        FastAPI 가 자체 검증 단계에서 422 Unprocessable Entity 를 반환해야 한다.
        유스케이스까지 도달해선 안 된다.
        """
        fake = FakeFindSimilarTickers(fixed_results=[])
        app = create_app(find_similar=fake)
        client = TestClient(app)

        response = client.get(
            "/similar/005930",
            params={
                # market 누락
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
            },
        )

        assert response.status_code == 422
        # 유스케이스가 호출되지 않아야 한다
        assert len(fake.recorded_queries) == 0


# ---------------------------------------------------------------------------
# 케이스 6: target 이 universe 에 없음 → 404
# ---------------------------------------------------------------------------

class TestSimilarEndpoint_404:
    def test_target이_유니버스에_없으면_404를_반환한다(self) -> None:
        """WHY: 유니버스에 없는 종목 요청은 클라이언트 입력 오류이므로
        404 Not Found 로 응답해야 한다. 500 으로 누출되면 안 된다.

        ValueError 메시지가 '대상 종목이 유니버스에 없습니다' 일 때 404 매핑.
        """
        fake = FakeFindSimilarTickers(
            raise_value_error="대상 종목이 유니버스에 없습니다"
        )
        app = create_app(find_similar=fake)
        client = TestClient(app)

        response = client.get(
            "/similar/UNKNOWN",
            params={
                "market": "KRX",
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
            },
        )

        assert response.status_code == 404
        body = response.json()
        assert "detail" in body


# ---------------------------------------------------------------------------
# 케이스 7: 기타 ValueError → 400
# ---------------------------------------------------------------------------

class TestSimilarEndpoint_400:
    def test_기타_ValueError는_400을_반환한다(self) -> None:
        """WHY: 유니버스 부재 외의 ValueError 는 잘못된 요청(400)으로 처리해야 한다.
        클라이언트가 수정 가능한 입력 오류를 의미하므로 500 으로 반환하면 안 된다.
        """
        fake = FakeFindSimilarTickers(
            raise_value_error="예상치 못한 입력 오류"
        )
        app = create_app(find_similar=fake)
        client = TestClient(app)

        response = client.get(
            "/similar/005930",
            params={
                "market": "KRX",
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
            },
        )

        assert response.status_code == 400
        body = response.json()
        assert "detail" in body
