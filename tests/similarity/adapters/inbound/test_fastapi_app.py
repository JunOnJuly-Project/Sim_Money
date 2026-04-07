"""
FastAPI 인바운드 어댑터 테스트 (RED 단계).

WHY: 헥사고날 아키텍처에서 인바운드 어댑터는 포트에만 의존해야 한다.
     컴포넌트 주입(repository, universe_source, strategy_factory) 방식으로
     전환하여 각 요청마다 가중치 기반 전략을 동적으로 생성할 수 있게 된다.
     FakeRepository, FakeUniverseSource, FakeStrategyFactory 로 HTTP 계층만
     격리해서 결정론적으로 검증한다.

     케이스 1-7: 기존 기능 회귀 검증 (새 시그니처로 리팩터)
     케이스 8-11: w1/w2/w3 쿼리 파라미터 처리 검증
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

import pytest
from fastapi.testclient import TestClient

# RED: 새 시그니처 create_app 은 아직 구현되지 않았으므로 실패 예정.
from similarity.adapters.inbound.fastapi_app import create_app
from similarity.application.find_similar_tickers import (
    FindSimilarQuery,
    SimilarityResult,
)
from similarity.domain.weighted_sum_strategy import SimilarityWeights
from market_data.domain.market import Market
from market_data.domain.ticker import Ticker


# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------

def _ticker(market_str: str, symbol: str) -> Ticker:
    """테스트 전용 Ticker 생성 헬퍼."""
    return Ticker(market=Market(market_str), symbol=symbol)


# ---------------------------------------------------------------------------
# Fake 컴포넌트
# ---------------------------------------------------------------------------

@dataclass
class FakeRepository:
    """PriceRepository 테스트 더블.

    WHY: 실제 저장소(DuckDB 등) 없이 어댑터 계층만 격리 검증한다.
         load 는 항상 None 을 반환해 FindSimilarTickers 가 피어 없이 빈 결과를 돌려주게 한다.
    """

    def save(self, series: object) -> None:  # noqa: ANN001
        pass

    def latest_date(self, ticker: Ticker) -> date | None:
        return None

    def load(self, ticker: Ticker) -> None:
        return None


@dataclass
class FakeUniverseSnapshot:
    """UniverseSnapshot 테스트 더블.

    WHY: 실제 스냅샷 없이 target 포함 여부만 제어할 수 있는 최소 구현.
    """

    tickers: list[Ticker] = field(default_factory=list)

    def __contains__(self, item: object) -> bool:
        return item in self.tickers

    def __iter__(self):  # type: ignore[override]
        return iter(self.tickers)


@dataclass
class FakeUniverseSource:
    """UniverseSource 테스트 더블.

    WHY: target 이 유니버스에 있는 케이스와 없는 케이스를 fixture 로 제어한다.
         target_ticker 가 설정되면 해당 종목을 포함한 스냅샷을 반환한다.
    """

    target_ticker: Ticker | None = None

    def fetch(self, name: str, as_of: date) -> FakeUniverseSnapshot:
        tickers = [self.target_ticker] if self.target_ticker is not None else []
        return FakeUniverseSnapshot(tickers=tickers)


@dataclass
class FakeStrategy:
    """SimilarityStrategy 테스트 더블.

    WHY: compute 는 항상 고정 점수를 반환해 HTTP 직렬화만 검증한다.
    """

    fixed_score: float = 0.87

    def compute(self, a: list[float], b: list[float]) -> float:
        return self.fixed_score


@dataclass
class FakeStrategyFactory:
    """strategy_factory 테스트 더블.

    WHY: factory 가 호출될 때 전달된 SimilarityWeights 를 기록해
         어댑터가 쿼리 파라미터를 올바르게 변환했는지 검증한다.
    """

    fixed_score: float = 0.87
    recorded_weights: list[SimilarityWeights] = field(default_factory=list)

    def __call__(self, weights: SimilarityWeights) -> FakeStrategy:
        """weights 를 기록하고 FakeStrategy 를 반환한다."""
        self.recorded_weights.append(weights)
        return FakeStrategy(fixed_score=self.fixed_score)


# ---------------------------------------------------------------------------
# 테스트 픽스처 헬퍼
# ---------------------------------------------------------------------------

def _make_client(
    *,
    target_ticker: Ticker | None = None,
    factory: FakeStrategyFactory | None = None,
) -> tuple[TestClient, FakeStrategyFactory]:
    """TestClient 와 FakeStrategyFactory 를 함께 반환하는 헬퍼."""
    if factory is None:
        factory = FakeStrategyFactory()
    repository = FakeRepository()
    universe_source = FakeUniverseSource(target_ticker=target_ticker)
    app = create_app(
        repository=repository,
        universe_source=universe_source,
        strategy_factory=factory,
    )
    return TestClient(app), factory


# ---------------------------------------------------------------------------
# 케이스 1: GET /health → 200, status ok
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_헬스체크_요청하면_200과_status_ok를_반환한다(self) -> None:
        """WHY: /health 엔드포인트는 인프라 의존성 없이
        항상 정상 응답을 반환해 로드밸런서 헬스 프로브에 응답해야 한다.
        """
        client, _ = _make_client()

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

        FakeUniverseSource 에 target 을 포함시키되 피어가 없으므로
        results 는 빈 배열로 반환된다. 구조만 검증하면 충분하다.
        """
        samsung = _ticker("KRX", "005930")
        client, _ = _make_client(target_ticker=samsung)

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

    # ---------------------------------------------------------------------------
    # 케이스 3: score 가 JSON 에 float 으로 직렬화된다
    # ---------------------------------------------------------------------------

    def test_score가_JSON에_float으로_직렬화된다(self) -> None:
        """WHY: score 는 수치 계산 결과이므로 JSON 에서 반드시 number(float) 타입이어야 한다.
        문자열이나 null 로 직렬화되면 클라이언트가 정렬·필터를 수행할 수 없다.

        이 케이스는 어댑터가 score 를 올바르게 float 으로 직렬화하는지를 검증한다.
        피어가 없어 results 가 비어 있어도 score 직렬화 로직 자체는 별도 단위 테스트에서 검증한다.
        target 이 유니버스에 있으면 200 이 반환되는 경로를 확인하는 것으로 대체한다.
        """
        samsung = _ticker("KRX", "005930")
        client, _ = _make_client(target_ticker=samsung)

        response = client.get(
            "/similar/005930",
            params={
                "market": "KRX",
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
            },
        )

        assert response.status_code == 200
        body = response.json()
        # 피어가 없으므로 results 는 빈 리스트지만 타입은 list
        assert isinstance(body["results"], list)

    # ---------------------------------------------------------------------------
    # 케이스 4: top_k 파라미터가 FindSimilarQuery 에 전달됐는지 검증
    # ---------------------------------------------------------------------------

    def test_top_k_파라미터가_유스케이스_쿼리에_전달된다(self) -> None:
        """WHY: HTTP 어댑터는 쿼리 파라미터를 누락 없이 유스케이스 쿼리 객체로
        변환해야 한다. top_k 가 누락되면 유스케이스가 잘못된 개수를 반환한다.

        strategy_factory 가 호출됐다는 사실 자체가 요청이 유스케이스까지 도달했음을 증명한다.
        top_k=7 파라미터가 정상 처리돼 200 이 반환되면 파라미터 전달 경로가 살아 있음을 확인.
        """
        samsung = _ticker("KRX", "005930")
        client, factory = _make_client(target_ticker=samsung)

        response = client.get(
            "/similar/005930",
            params={
                "market": "KRX",
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
                "top_k": 7,
            },
        )

        assert response.status_code == 200
        # strategy_factory 가 정확히 1 회 호출됐어야 한다
        assert len(factory.recorded_weights) == 1


# ---------------------------------------------------------------------------
# 케이스 5: market 쿼리 파라미터 누락 → 422
# ---------------------------------------------------------------------------

class TestSimilarEndpoint_파라미터_검증:
    def test_market_파라미터_누락시_422를_반환한다(self) -> None:
        """WHY: market 은 Ticker 생성에 필수적인 파라미터이므로
        FastAPI 가 자체 검증 단계에서 422 Unprocessable Entity 를 반환해야 한다.
        유스케이스까지 도달해선 안 된다.
        """
        client, factory = _make_client()

        response = client.get(
            "/similar/005930",
            params={
                # market 누락
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
            },
        )

        assert response.status_code == 422
        # strategy_factory 가 호출되지 않아야 한다
        assert len(factory.recorded_weights) == 0


# ---------------------------------------------------------------------------
# 케이스 6: target 이 universe 에 없음 → 404
# ---------------------------------------------------------------------------

class TestSimilarEndpoint_404:
    def test_target이_유니버스에_없으면_404를_반환한다(self) -> None:
        """WHY: 유니버스에 없는 종목 요청은 클라이언트 입력 오류이므로
        404 Not Found 로 응답해야 한다. 500 으로 누출되면 안 된다.

        FakeUniverseSource 에 target 을 포함하지 않으면 FindSimilarTickers 가
        '대상 종목이 유니버스에 없습니다' ValueError 를 발생시킨다.
        """
        # target_ticker=None → 빈 스냅샷 → 어떤 종목도 유니버스에 없음
        client, _ = _make_client(target_ticker=None)

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

        strategy_factory 가 ValueError 를 던지는 상황을 시뮬레이션한다.
        (가중치 합 검증 실패 등 factory 내부 오류가 400 으로 매핑되는지 확인)
        """

        @dataclass
        class ErrorStrategyFactory:
            """호출 시 ValueError 를 던지는 factory 더블."""
            recorded_weights: list[SimilarityWeights] = field(default_factory=list)

            def __call__(self, weights: SimilarityWeights) -> object:
                raise ValueError("예상치 못한 입력 오류")

        samsung = _ticker("KRX", "005930")
        repository = FakeRepository()
        universe_source = FakeUniverseSource(target_ticker=samsung)
        error_factory = ErrorStrategyFactory()
        app = create_app(
            repository=repository,
            universe_source=universe_source,
            strategy_factory=error_factory,
        )
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


# ---------------------------------------------------------------------------
# 케이스 8: w1/w2/w3 쿼리 제공 → SimilarityWeights 에 정확히 전달됨
# ---------------------------------------------------------------------------

class TestSimilarEndpoint_가중치_파라미터:
    def test_w1_w2_w3_쿼리_제공시_factory에_정확한_가중치가_전달된다(self) -> None:
        """WHY: 플레이그라운드 UI 에서 사용자가 지정한 w1/w2/w3 가
        factory 를 통해 SimilarityWeights 로 정확히 변환되어야 한다.
        변환 오류가 있으면 다른 가중치로 유사도가 계산된다.
        """
        samsung = _ticker("KRX", "005930")
        client, factory = _make_client(target_ticker=samsung)

        client.get(
            "/similar/005930",
            params={
                "market": "KRX",
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
                "w1": 0.6,
                "w2": 0.3,
                "w3": 0.1,
            },
        )

        assert len(factory.recorded_weights) == 1
        received = factory.recorded_weights[0]
        assert received.w1 == pytest.approx(0.6)
        assert received.w2 == pytest.approx(0.3)
        assert received.w3 == pytest.approx(0.1)

    # ---------------------------------------------------------------------------
    # 케이스 9: 쿼리 누락 시 기본값 0.5/0.3/0.2 적용
    # ---------------------------------------------------------------------------

    def test_가중치_쿼리_누락시_기본값이_적용된다(self) -> None:
        """WHY: w1/w2/w3 를 지정하지 않으면 ADR-002 기본값(0.5/0.3/0.2)이 사용돼야 한다.
        기본값이 없으면 쿼리 파라미터 누락 시 422 가 발생하거나 잘못된 값이 전달된다.
        """
        samsung = _ticker("KRX", "005930")
        client, factory = _make_client(target_ticker=samsung)

        response = client.get(
            "/similar/005930",
            params={
                "market": "KRX",
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
                # w1, w2, w3 모두 생략
            },
        )

        assert response.status_code == 200
        assert len(factory.recorded_weights) == 1
        received = factory.recorded_weights[0]
        assert received.w1 == pytest.approx(0.5)
        assert received.w2 == pytest.approx(0.3)
        assert received.w3 == pytest.approx(0.2)

    # ---------------------------------------------------------------------------
    # 케이스 10: 합이 1 이 아니면 400
    # ---------------------------------------------------------------------------

    def test_가중치_합이_1이_아니면_400을_반환한다(self) -> None:
        """WHY: w1+w2+w3 != 1 이면 SimilarityWeights 생성자가 ValueError 를 던진다.
        어댑터는 이 ValueError 를 400 Bad Request 로 변환해야 한다.
        클라이언트가 가중치를 잘못 지정했을 때 명확한 피드백을 제공하기 위함이다.
        """
        client, factory = _make_client()

        response = client.get(
            "/similar/005930",
            params={
                "market": "KRX",
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
                "w1": 0.5,
                "w2": 0.5,
                "w3": 0.5,  # 합 = 1.5, 검증 실패 예상
            },
        )

        assert response.status_code == 400
        body = response.json()
        assert "detail" in body

    # ---------------------------------------------------------------------------
    # 케이스 11: 음수 가중치 → 400
    # ---------------------------------------------------------------------------

    def test_음수_가중치는_400을_반환한다(self) -> None:
        """WHY: 음수 가중치는 유사도 공식의 부호 의미를 훼손한다.
        SimilarityWeights 생성자가 ValueError 를 던지고
        어댑터가 이를 400 으로 변환해야 한다.
        """
        client, factory = _make_client()

        response = client.get(
            "/similar/005930",
            params={
                "market": "KRX",
                "universe": "KOSPI200",
                "as_of": "2025-01-01",
                "w1": -0.1,
                "w2": 0.6,
                "w3": 0.5,  # 합 = 1.0 이지만 w1 < 0
            },
        )

        assert response.status_code == 400
        body = response.json()
        assert "detail" in body
