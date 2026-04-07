"""
로그수익률 값 객체.

WHY: 로그수익률은 시계열 합산이 가능하고 정규분포에 가까워
     포트폴리오 최적화에서 표준 입력으로 사용한다.
     NaN/Inf 는 이후 행렬 연산을 오염시키므로 생성 시점에 차단한다.
"""
import math
from dataclasses import dataclass

from .adjusted_price import AdjustedPrice


@dataclass(frozen=True)
class LogReturn:
    """로그수익률 ln(p_t / p_{t-1}). 유한값만 허용."""

    value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError(f"LogReturn 은 유한값이어야 합니다: {self.value}")

    @classmethod
    def from_prices(cls, prev: AdjustedPrice, curr: AdjustedPrice) -> "LogReturn":
        """이전/현재 수정주가로부터 로그수익률을 계산한다.

        전제조건: prev.value > 0, curr.value > 0 은 ``AdjustedPrice`` 의
        불변식에 의해 보장되므로 여기서는 재검증하지 않는다.
        """
        ratio = float(curr.value) / float(prev.value)
        return cls(value=math.log(ratio))
