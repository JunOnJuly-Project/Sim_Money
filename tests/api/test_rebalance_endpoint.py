"""
POST /portfolio/rebalance 엔드포인트 통합 테스트.

WHY: PlanRebalance 유스케이스를 HTTP 계층까지 일관되게 검증해
     DTO 변환 오류, 도메인 불변식 위반, 임계값 필터링을 조기에 발견한다.
     Fake 주입으로 저장소 의존 없이 순수 HTTP 어댑터 동작만 검증한다.

케이스:
    1. 신규 진입 — current 비어있고 target 1개
    2. 청산 — current 1개 + 동일 symbol target=0.0
    3. 부분 리밸런싱 — BUY/SELL 혼재
    4. min_trade_weight 미만 delta 는 무시
    5. 빈 입력 → 빈 intents
    6. total_equity=0 → 400
    7. target weight > 1 → 400
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest
from fastapi.testclient import TestClient

from market_data.domain.market import Market
from market_data.domain.ticker import Ticker
from similarity.adapters.inbound.fastapi_app import create_app
from similarity.domain.weighted_sum_strategy import SimilarityWeights

# ── 상수 ─────────────────────────────────────────────────────────────────

_TOTAL_EQUITY_DEFAULT = 100_000.0
_SYMBOL_A = "AAPL"
_SYMBOL_B = "MSFT"


# ── Fake 컴포넌트 ──────────────────────────────────────────────────────────

@dataclass
class _FakePriceRepository:
    """테스트에서 사용되지 않는 PriceRepository 더미."""

    def load(self, ticker: Ticker) -> None:
        return None

    def latest_date(self, ticker: Ticker) -> None:
        return None


@dataclass
class _FakeUniverseSource:
    """테스트에서 사용되지 않는 UniverseSource 더미."""

    def fetch(self, name: str, as_of: date) -> object:
        raise NotImplementedError


class _FakeStrategyFactory:
    """테스트에서 사용되지 않는 strategy_factory 더미."""

    def __call__(self, weights: SimilarityWeights) -> object:
        raise NotImplementedError


# ── 픽스처 ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client() -> TestClient:
    """create_app 에 Fake 의존성을 주입한 TestClient."""
    app = create_app(
        repository=_FakePriceRepository(),
        universe_source=_FakeUniverseSource(),
        strategy_factory=_FakeStrategyFactory(),
    )
    return TestClient(app)


def _post(client: TestClient, payload: dict) -> object:
    """POST /portfolio/rebalance 헬퍼."""
    return client.post("/portfolio/rebalance", json=payload)


# ── 테스트 케이스 ─────────────────────────────────────────────────────────


def test_신규_진입_BUY_의도_반환(client: TestClient) -> None:
    """current 없이 target 비중만 있으면 BUY intent 가 반환된다."""
    payload = {
        "current_positions": [],
        "target_weights": [{"symbol": _SYMBOL_A, "weight": 0.5}],
        "total_equity": _TOTAL_EQUITY_DEFAULT,
    }
    res = _post(client, payload)

    assert res.status_code == 200
    intents = res.json()["intents"]
    assert len(intents) == 1
    assert intents[0]["symbol"] == _SYMBOL_A
    assert intents[0]["side"] == "BUY"
    assert abs(intents[0]["delta_weight"] - 0.5) < 1e-9


def test_청산_SELL_의도_반환(client: TestClient) -> None:
    """current 에 포지션 있고 target=0.0 이면 SELL intent 가 반환된다."""
    payload = {
        "current_positions": [
            {"symbol": _SYMBOL_A, "quantity": 10.0, "market_value": 50_000.0}
        ],
        "target_weights": [{"symbol": _SYMBOL_A, "weight": 0.0}],
        "total_equity": _TOTAL_EQUITY_DEFAULT,
    }
    res = _post(client, payload)

    assert res.status_code == 200
    intents = res.json()["intents"]
    assert len(intents) == 1
    assert intents[0]["symbol"] == _SYMBOL_A
    assert intents[0]["side"] == "SELL"
    assert intents[0]["delta_weight"] < 0


def test_부분_리밸런싱_BUY_SELL_혼재(client: TestClient) -> None:
    """A 과소·B 과다 보유 시 A=BUY, B=SELL 의도가 모두 반환된다."""
    payload = {
        "current_positions": [
            {"symbol": _SYMBOL_A, "quantity": 5.0, "market_value": 20_000.0},
            {"symbol": _SYMBOL_B, "quantity": 5.0, "market_value": 60_000.0},
        ],
        "target_weights": [
            {"symbol": _SYMBOL_A, "weight": 0.5},
            {"symbol": _SYMBOL_B, "weight": 0.3},
        ],
        "total_equity": _TOTAL_EQUITY_DEFAULT,
    }
    res = _post(client, payload)

    assert res.status_code == 200
    intents = res.json()["intents"]
    sides = {i["symbol"]: i["side"] for i in intents}
    assert sides[_SYMBOL_A] == "BUY"
    assert sides[_SYMBOL_B] == "SELL"


def test_임계값_미만_delta_무시(client: TestClient) -> None:
    """delta 가 min_trade_weight 미만이면 intent 가 생성되지 않는다."""
    # current 40%, target 40.5% → delta 0.5% < min_trade_weight 1%
    payload = {
        "current_positions": [
            {"symbol": _SYMBOL_A, "quantity": 10.0, "market_value": 40_000.0}
        ],
        "target_weights": [{"symbol": _SYMBOL_A, "weight": 0.405}],
        "total_equity": _TOTAL_EQUITY_DEFAULT,
        "min_trade_weight": 0.01,
    }
    res = _post(client, payload)

    assert res.status_code == 200
    assert res.json()["intents"] == []


def test_빈_입력_빈_intents(client: TestClient) -> None:
    """current/target 모두 비어있으면 빈 intents 를 반환한다."""
    payload = {
        "current_positions": [],
        "target_weights": [],
        "total_equity": _TOTAL_EQUITY_DEFAULT,
    }
    res = _post(client, payload)

    assert res.status_code == 200
    assert res.json()["intents"] == []


def test_total_equity_0_400(client: TestClient) -> None:
    """total_equity=0 이면 400 을 반환한다."""
    payload = {
        "current_positions": [],
        "target_weights": [{"symbol": _SYMBOL_A, "weight": 0.5}],
        "total_equity": 0,
    }
    res = _post(client, payload)

    assert res.status_code == 400


def test_target_weight_초과_400(client: TestClient) -> None:
    """target weight > 1 이면 도메인 ValueError → 400 을 반환한다."""
    payload = {
        "current_positions": [],
        "target_weights": [{"symbol": _SYMBOL_A, "weight": 1.5}],
        "total_equity": _TOTAL_EQUITY_DEFAULT,
    }
    res = _post(client, payload)

    assert res.status_code == 400
