"""
POST /portfolio/compute 엔드포인트 통합 테스트.

WHY: ComputeTargetWeights 유스케이스를 HTTP 계층까지 일관되게 검증해
     DTO 변환 오류, 도메인 불변식 위반, 전략 분기 로직을 조기에 발견한다.
     Fake 주입으로 저장소 의존 없이 순수 HTTP 어댑터 동작만 검증한다.

케이스:
    1. equal_weight 기본 — 균등 비중 반환
    2. score_weighted 차등 — score 비례 비중 반환
    3. cash_buffer=0.2 → 비중 합 ≈ 0.8
    4. max_position_weight 캡 적용
    5. 빈 signals → 빈 weights
    6. 음수 score → 400
    7. 잘못된 strategy 이름 → 422 (Pydantic Literal)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest
from fastapi.testclient import TestClient

from market_data.domain.ticker import Ticker
from similarity.adapters.inbound.fastapi_app import create_app
from similarity.domain.weighted_sum_strategy import SimilarityWeights

# ── 상수 ─────────────────────────────────────────────────────────────────

_SYMBOL_A = "AAPL"
_SYMBOL_B = "MSFT"
_SYMBOL_C = "GOOG"
_WEIGHT_SUM_TOLERANCE = 1e-6
_CASH_BUFFER_20 = 0.2
_EXPECTED_SUM_WITH_CASH_BUFFER = 0.8
_MAX_POSITION_CAP = 0.3


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
    """POST /portfolio/compute 헬퍼."""
    return client.post("/portfolio/compute", json=payload)


# ── 테스트 케이스 ─────────────────────────────────────────────────────────


def test_equal_weight_기본_균등_비중_반환(client: TestClient) -> None:
    """equal_weight 전략은 모든 종목에 동일한 비중을 부여한다."""
    payload = {
        "signals": [
            {"symbol": _SYMBOL_A, "score": 1.0},
            {"symbol": _SYMBOL_B, "score": 2.0},
        ],
        "strategy": "equal_weight",
    }
    res = _post(client, payload)

    assert res.status_code == 200
    weights = res.json()["weights"]
    assert len(weights) == 2
    weight_values = [w["weight"] for w in weights]
    # 균등 비중이므로 모든 값이 동일해야 한다
    assert abs(weight_values[0] - weight_values[1]) < _WEIGHT_SUM_TOLERANCE
    # 합이 1.0 이어야 한다
    assert abs(sum(weight_values) - 1.0) < _WEIGHT_SUM_TOLERANCE


def test_score_weighted_차등_비중_반환(client: TestClient) -> None:
    """score_weighted 전략은 score 비례로 비중을 차등 부여한다."""
    payload = {
        "signals": [
            {"symbol": _SYMBOL_A, "score": 1.0},
            {"symbol": _SYMBOL_B, "score": 3.0},
        ],
        "strategy": "score_weighted",
    }
    res = _post(client, payload)

    assert res.status_code == 200
    weights_map = {w["symbol"]: w["weight"] for w in res.json()["weights"]}
    # MSFT(score=3) 이 AAPL(score=1) 보다 3배 높아야 한다
    assert weights_map[_SYMBOL_B] > weights_map[_SYMBOL_A]
    ratio = weights_map[_SYMBOL_B] / weights_map[_SYMBOL_A]
    assert abs(ratio - 3.0) < 1e-6


def test_cash_buffer_적용_비중_합이_0_8(client: TestClient) -> None:
    """cash_buffer=0.2 일 때 비중 합이 약 0.8 이어야 한다."""
    payload = {
        "signals": [
            {"symbol": _SYMBOL_A, "score": 1.0},
            {"symbol": _SYMBOL_B, "score": 1.0},
        ],
        "strategy": "equal_weight",
        "cash_buffer": _CASH_BUFFER_20,
    }
    res = _post(client, payload)

    assert res.status_code == 200
    total = sum(w["weight"] for w in res.json()["weights"])
    assert abs(total - _EXPECTED_SUM_WITH_CASH_BUFFER) < _WEIGHT_SUM_TOLERANCE


def test_max_position_weight_캡_적용(client: TestClient) -> None:
    """max_position_weight=0.3 이면 모든 종목 비중이 0.3 이하여야 한다."""
    payload = {
        "signals": [
            {"symbol": _SYMBOL_A, "score": 1.0},
            {"symbol": _SYMBOL_B, "score": 1.0},
        ],
        "strategy": "equal_weight",
        "max_position_weight": _MAX_POSITION_CAP,
    }
    res = _post(client, payload)

    assert res.status_code == 200
    for w in res.json()["weights"]:
        assert w["weight"] <= _MAX_POSITION_CAP + _WEIGHT_SUM_TOLERANCE


def test_빈_signals_빈_weights(client: TestClient) -> None:
    """signals 가 비어있으면 weights 도 비어있어야 한다."""
    payload = {
        "signals": [],
        "strategy": "equal_weight",
    }
    res = _post(client, payload)

    assert res.status_code == 200
    assert res.json()["weights"] == []


def test_음수_score_400(client: TestClient) -> None:
    """음수 score 는 도메인 ValueError → HTTP 400 을 반환한다."""
    payload = {
        "signals": [
            {"symbol": _SYMBOL_A, "score": -1.0},
        ],
        "strategy": "score_weighted",
    }
    res = _post(client, payload)

    assert res.status_code == 400


def test_잘못된_strategy_422(client: TestClient) -> None:
    """Literal 에 없는 strategy 이름은 Pydantic 검증 오류 → 422 를 반환한다."""
    payload = {
        "signals": [
            {"symbol": _SYMBOL_A, "score": 1.0},
        ],
        "strategy": "invalid_strategy",
    }
    res = _post(client, payload)

    assert res.status_code == 422
