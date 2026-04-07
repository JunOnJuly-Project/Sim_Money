"""
OHLCV 가격 봉 값 객체.

WHY: 가격 이력은 사실(fact)이므로 생성 후 절대 변경되어서는 안 된다.
     frozen dataclass 로 불변성을 컴파일 수준에서 보장하고,
     __post_init__ 에서 OHLCV 물리적 불변식을 검증해
     손상된 시장 데이터가 파이프라인에 전파되는 것을 차단한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PriceBar:
    """단일 시간 단위의 OHLCV 가격 봉."""

    timestamp: datetime
    ticker: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        """OHLCV 물리적 불변식 검증."""
        if not self.ticker:
            raise ValueError("ticker 는 빈 문자열일 수 없습니다.")
        if self.high < self.low:
            raise ValueError("high 는 low 보다 크거나 같아야 합니다.")
        if self.high < self.open:
            raise ValueError("high 는 open 보다 크거나 같아야 합니다.")
        if self.high < self.close:
            raise ValueError("high 는 close 보다 크거나 같아야 합니다.")
        if self.low > self.open:
            raise ValueError("low 는 open 보다 작거나 같아야 합니다.")
        if self.low > self.close:
            raise ValueError("low 는 close 보다 작거나 같아야 합니다.")
        if self.volume < Decimal("0"):
            raise ValueError("volume 은 0 이상이어야 합니다.")
