"""
Ticker 값 객체.

WHY: 종목 식별자는 시스템 전반에서 동등성 비교·해시·직렬화가 필요하므로
     불변 frozen dataclass 로 정의해 실수에 의한 변경을 원천 차단한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from market_data.domain.market import Market

_SEPARATOR = ":"


@dataclass(frozen=True)
class Ticker:
    """거래소 + 종목 코드의 불변 값 객체."""

    market: Market
    symbol: str

    def __post_init__(self) -> None:
        # frozen=True 이므로 object.__setattr__ 로 정규화
        normalized = self.symbol.strip().upper()
        if not normalized:
            raise ValueError(f"심볼은 공백이거나 빈 문자열일 수 없습니다: {self.symbol!r}")
        object.__setattr__(self, "symbol", normalized)

    @classmethod
    def from_string(cls, s: str) -> "Ticker":
        """'MARKET:SYMBOL' 형식 문자열을 Ticker 로 변환한다."""
        parts = s.split(_SEPARATOR, maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"Ticker 문자열 형식 오류 (예: 'KRX:005930'): {s!r}")
        market_str, symbol = parts
        try:
            market = Market(market_str.upper())
        except ValueError as exc:
            raise ValueError(f"지원하지 않는 시장입니다: {market_str!r}") from exc
        return cls(market=market, symbol=symbol)

    def __str__(self) -> str:
        return f"{self.market.value}{_SEPARATOR}{self.symbol}"
