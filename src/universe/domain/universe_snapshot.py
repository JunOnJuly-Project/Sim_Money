"""
UniverseSnapshot 애그리거트 (불변 값 객체).

WHY: 유니버스는 특정 날짜(as_of) 기준으로 투자 대상 종목 집합을 확정한다.
     frozen dataclass 로 불변성을 보장해 생존편향(survivorship bias) 분석 시
     과거 시점 스냅샷이 의도치 않게 변경되는 것을 원천 차단한다.

생존편향: 특정 날짜 이후 상장폐지된 종목은 해당 날짜의 스냅샷에 포함되어야
          한다. 이를 위해 스냅샷은 as_of 날짜 기준 그대로 보존되어야 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterator

from market_data.domain.ticker import Ticker

# 오류 메시지 상수 — 매직 문자열 금지
_ERR_NAME_EMPTY = "name 은 공백이거나 빈 문자열일 수 없습니다."
_ERR_TICKERS_EMPTY = "tickers 는 하나 이상의 종목을 포함해야 합니다."
_ERR_TICKERS_DUPLICATE = "중복된 ticker 가 존재합니다: {duplicates}"
_ERR_AS_OF_MISMATCH = "as_of 날짜가 다른 스냅샷은 union 할 수 없습니다: {a} vs {b}"


@dataclass(frozen=True)
class UniverseSnapshot:
    """특정 날짜 기준의 투자 대상 유니버스 스냅샷.

    WHY: frozen=True 로 불변 보장 — 생존편향 분석 시 과거 스냅샷이 오염되지 않도록.
    """

    name: str
    as_of: date
    tickers: tuple[Ticker, ...]

    def __post_init__(self) -> None:
        """불변식 검증 및 입력 정규화."""
        self._정규화_name()
        self._검증_name()
        self._정규화_tickers()
        self._검증_tickers_비어있지_않음()
        self._검증_tickers_중복없음()

    def _정규화_name(self) -> None:
        """name 앞뒤 공백을 제거한다."""
        object.__setattr__(self, "name", self.name.strip())

    def _검증_name(self) -> None:
        if not self.name:
            raise ValueError(_ERR_NAME_EMPTY)

    def _정규화_tickers(self) -> None:
        """list 입력을 tuple 로 정규화한다."""
        if not isinstance(self.tickers, tuple):
            object.__setattr__(self, "tickers", tuple(self.tickers))

    def _검증_tickers_비어있지_않음(self) -> None:
        if not self.tickers:
            raise ValueError(_ERR_TICKERS_EMPTY)

    def _검증_tickers_중복없음(self) -> None:
        seen: set[Ticker] = set()
        duplicates: list[Ticker] = []
        for ticker in self.tickers:
            if ticker in seen:
                duplicates.append(ticker)
            seen.add(ticker)
        if duplicates:
            raise ValueError(_ERR_TICKERS_DUPLICATE.format(duplicates=duplicates))

    # ------------------------------------------------------------------
    # 컬렉션 프로토콜
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """포함된 종목 수를 반환한다."""
        return len(self.tickers)

    def __contains__(self, item: object) -> bool:
        """in 연산자로 특정 ticker 포함 여부를 확인한다."""
        return item in self.tickers

    def __iter__(self) -> Iterator[Ticker]:
        """for-loop 로 모든 종목을 순회할 수 있게 한다."""
        return iter(self.tickers)

    # ------------------------------------------------------------------
    # 도메인 메서드
    # ------------------------------------------------------------------

    def union(self, other: UniverseSnapshot) -> UniverseSnapshot:
        """같은 as_of 날짜의 두 스냅샷을 합집합으로 합친다.

        WHY: 날짜가 다른 유니버스의 합집합은 시점이 혼재되어
             생존편향 분석 결과가 오염된다. 따라서 as_of 불일치 시 거부한다.

        Args:
            other: 합칠 대상 스냅샷.

        Returns:
            합집합 스냅샷. name 은 '{self.name}+{other.name}' 형식.

        Raises:
            ValueError: as_of 날짜가 다를 때.
        """
        if self.as_of != other.as_of:
            raise ValueError(
                _ERR_AS_OF_MISMATCH.format(a=self.as_of, b=other.as_of)
            )
        merged_tickers = self._합집합_순서보존(other.tickers)
        return UniverseSnapshot(
            name=f"{self.name}+{other.name}",
            as_of=self.as_of,
            tickers=merged_tickers,
        )

    def _합집합_순서보존(self, other_tickers: tuple[Ticker, ...]) -> tuple[Ticker, ...]:
        """순서를 보존하며 중복 없는 합집합 tuple 을 반환한다."""
        seen: set[Ticker] = set()
        result: list[Ticker] = []
        for ticker in (*self.tickers, *other_tickers):
            if ticker not in seen:
                seen.add(ticker)
                result.append(ticker)
        return tuple(result)

    def is_survivor(self, ticker: Ticker) -> bool:
        """해당 ticker 가 이 스냅샷(as_of 기준)에 살아남았는지 반환한다.

        WHY: 생존편향 제거를 위해 특정 날짜 기준으로 종목이 유니버스에
             포함되었는지 명시적으로 확인한다.
        """
        return ticker in self
