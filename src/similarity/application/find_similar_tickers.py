"""
유사 종목 탐색 유스케이스.

WHY: 헥사고날 아키텍처에서 유스케이스는 포트(Protocol)에만 의존해야 한다.
     PriceRepository, UniverseSource, SimilarityStrategy 세 포트를 주입받아
     인프라 구현 교체 시 이 파일을 수정하지 않아도 되도록 DIP 를 준수한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from market_data.application.ports import PriceRepository
from market_data.domain.ticker import Ticker

# 오류 메시지 상수 — 매직 문자열 금지
_ERR_TARGET_NOT_IN_UNIVERSE = "대상 종목이 유니버스에 없습니다"
_ERR_TARGET_SERIES_MISSING = "대상 종목의 시계열 없음"
_ERR_TARGET_RETURNS_EMPTY = "대상 종목의 로그수익률이 비어 있습니다"

# 유효한 피어 로그수익률 최소 길이
_MIN_PEER_RETURNS_LENGTH = 2

# top_k 기본값
_DEFAULT_TOP_K = 10


class UniverseSource(Protocol):
    """유니버스 스냅샷 조회 포트.

    WHY: 실제 저장소(DB, 파일 등) 구현 없이 유스케이스를
         독립적으로 테스트할 수 있도록 Protocol 로 추상화한다.
    """

    def fetch(self, name: str, as_of: date) -> object:
        """이름과 날짜 기준 유니버스 스냅샷을 반환한다."""
        ...


class SimilarityStrategy(Protocol):
    """유사도 계산 전략 포트.

    WHY: ADR-002 에 따라 공식을 이 포트로만 호출해
         구현 교체 시 유스케이스 코드를 변경하지 않아도 된다.
    """

    def compute(self, a: list[float], b: list[float]) -> float:
        """두 수치 시퀀스의 유사도 점수를 계산한다."""
        ...


@dataclass(frozen=True)
class FindSimilarQuery:
    """유사 종목 탐색 쿼리 값 객체.

    WHY: frozen dataclass 로 불변성을 보장해 동일 쿼리를
         여러 번 실행해도 입력이 오염되지 않도록 한다.
    """

    target: Ticker
    universe_name: str
    as_of: date
    top_k: int = _DEFAULT_TOP_K
    min_abs_score: float = 0.0


@dataclass(frozen=True)
class SimilarityResult:
    """유사도 탐색 결과 값 객체."""

    ticker: Ticker
    score: float


@dataclass(frozen=True)
class FindSimilarTickers:
    """유사 종목 탐색 유스케이스.

    WHY: frozen dataclass 로 의존성 주입 후 상태 변이를 차단한다.
         동일 인스턴스를 여러 번 실행해도 부작용이 없다.
    """

    repository: object  # PriceRepository 포트
    universe_source: object  # UniverseSource 포트
    strategy: object  # SimilarityStrategy 포트

    def execute(self, query: FindSimilarQuery) -> list[SimilarityResult]:
        """유사 종목 목록을 반환한다.

        Args:
            query: 탐색 조건을 담은 쿼리 객체.

        Returns:
            |score| 내림차순으로 정렬된 SimilarityResult 목록 (최대 top_k 개).

        Raises:
            ValueError: target 이 유니버스에 없거나 시계열이 없을 때.
        """
        snapshot = self.universe_source.fetch(query.universe_name, query.as_of)
        self._검증_target_in_universe(query.target, snapshot)

        target_returns = self._load_target_returns(query.target)
        results = self._collect_peer_results(query, snapshot, target_returns)
        return self._정렬_후_top_k_반환(results, query.top_k)

    def _검증_target_in_universe(self, target: Ticker, snapshot: object) -> None:
        """target 이 유니버스 스냅샷에 포함되어 있는지 검증한다."""
        if target not in snapshot:
            raise ValueError(_ERR_TARGET_NOT_IN_UNIVERSE)

    def _load_target_returns(self, target: Ticker) -> tuple[float, ...]:
        """target 의 로그수익률을 로드하고 최소 길이를 검증한다."""
        target_series = self.repository.load(target)
        if target_series is None:
            raise ValueError(_ERR_TARGET_SERIES_MISSING)

        returns = tuple(r.value for r in target_series.log_returns())
        if len(returns) < 1:
            raise ValueError(_ERR_TARGET_RETURNS_EMPTY)
        return returns

    def _collect_peer_results(
        self,
        query: FindSimilarQuery,
        snapshot: object,
        target_returns: tuple[float, ...],
    ) -> list[SimilarityResult]:
        """유니버스 내 피어 종목별 유사도를 계산해 필터링된 결과를 모은다."""
        results: list[SimilarityResult] = []
        for peer in snapshot:
            if peer == query.target:
                continue
            result = self._피어_유사도_계산(peer, target_returns, query.min_abs_score)
            if result is not None:
                results.append(result)
        return results

    def _피어_유사도_계산(
        self,
        peer: Ticker,
        target_returns: tuple[float, ...],
        min_abs_score: float,
    ) -> SimilarityResult | None:
        """단일 피어의 유사도를 계산한다. 스킵 조건이면 None 반환."""
        peer_series = self.repository.load(peer)
        if peer_series is None:
            return None

        peer_returns = tuple(r.value for r in peer_series.log_returns())
        if not self._is_returns_compatible(peer_returns, target_returns):
            return None

        try:
            score = self.strategy.compute(target_returns, peer_returns)
        except ValueError:
            return None

        if abs(score) < min_abs_score:
            return None
        return SimilarityResult(peer, score)

    def _is_returns_compatible(
        self,
        peer_returns: tuple[float, ...],
        target_returns: tuple[float, ...],
    ) -> bool:
        """피어 수익률이 유사도 계산에 호환 가능한지 확인한다.

        WHY: 길이가 2 미만이면 통계적으로 의미가 없고,
             target 과 길이가 다르면 인덱스 기반 비교가 불가능하다.
        """
        return (
            len(peer_returns) >= _MIN_PEER_RETURNS_LENGTH
            and len(peer_returns) == len(target_returns)
        )

    def _정렬_후_top_k_반환(
        self,
        results: list[SimilarityResult],
        top_k: int,
    ) -> list[SimilarityResult]:
        """절대값 점수 내림차순으로 정렬 후 top_k 개만 반환한다."""
        sorted_results = sorted(results, key=lambda r: abs(r.score), reverse=True)
        return sorted_results[:top_k]
