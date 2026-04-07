"""
수정주가 값 객체.

WHY: 액면분할·배당이 반영된 수정주가는 항상 양수여야 한다.
     이 불변식을 타입 수준에서 강제해 잘못된 가격 전파를 방지한다.
"""
import math
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AdjustedPrice:
    """수정주가 (액면분할·배당 반영). 반드시 양수."""

    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise TypeError("AdjustedPrice.value 는 Decimal 이어야 합니다")
        if self.value <= 0:
            raise ValueError(f"AdjustedPrice 는 양수여야 합니다: {self.value}")

    @classmethod
    def from_float(cls, f: float) -> "AdjustedPrice":
        """float 로부터 AdjustedPrice 를 생성한다. NaN/Inf/음수 거부."""
        if math.isnan(f) or math.isinf(f):
            raise ValueError(f"AdjustedPrice 는 유한한 양수여야 합니다: {f}")
        if f <= 0:
            raise ValueError(f"AdjustedPrice 는 양수여야 합니다: {f}")
        return cls(value=Decimal(str(f)))
