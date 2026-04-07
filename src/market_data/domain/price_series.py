"""
PriceSeries 애그리거트.

WHY: 시계열 가격 데이터는 날짜 오름차순·중복 없음·비어있지 않음이라는
     불변식이 항상 성립해야 한다. 이 불변식을 애그리거트 생성 시점에
     강제함으로써 하위 연산(로그수익률, 충분성 판단)에서 방어 코드를 제거한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from market_data.domain.adjusted_price import AdjustedPrice
from market_data.domain.log_return import LogReturn
from market_data.domain.ticker import Ticker

# 1거래년도 표준 영업일 수 — 충분성 판단 기본 기준
_DEFAULT_MIN_OBS: int = 252


@dataclass(frozen=True)
class PriceSeries:
    """종목(Ticker) 에 대응하는 날짜별 수정주가 시계열 애그리거트.

    prices: (date, AdjustedPrice) 쌍의 tuple. 날짜 오름차순, 중복 없음, 비어있지 않음.
    """

    ticker: Ticker
    prices: tuple[tuple[date, AdjustedPrice], ...]

    def __post_init__(self) -> None:
        """불변식 검증 및 list 입력 정규화.

        WHY: frozen=True 이므로 object.__setattr__ 로만 필드를 수정할 수 있다.
             list 로 넘어온 입력을 tuple 로 정규화해 외부 변이 가능성을 차단한다.
        """
        # list → tuple 정규화 (사용자가 list 를 넘기는 실수 방지)
        normalized = tuple(self.prices)
        object.__setattr__(self, "prices", normalized)

        self._validate_non_empty()
        self._validate_dates_ascending()

    def _validate_non_empty(self) -> None:
        """빈 시계열을 거부한다."""
        if len(self.prices) == 0:
            raise ValueError("PriceSeries 는 최소 1개의 가격을 가져야 합니다")

    def _validate_dates_ascending(self) -> None:
        """날짜가 오름차순이 아니거나 중복인 경우를 거부한다."""
        dates = [d for d, _ in self.prices]
        for prev, curr in zip(dates, dates[1:]):
            if curr == prev:
                raise ValueError(f"날짜 중복이 허용되지 않습니다: {curr}")
            if curr < prev:
                raise ValueError(
                    f"날짜가 오름차순이어야 합니다: {prev} → {curr}"
                )

    def __len__(self) -> int:
        """시계열 길이(가격 개수)를 반환한다."""
        return len(self.prices)

    def log_returns(self) -> tuple[LogReturn, ...]:
        """연속 수정주가로부터 로그수익률 시계열을 계산한다.

        WHY: ln(p_t / p_{t-1}) 는 시간 가산성이 있어 포트폴리오 계산에 표준이다.
             결과 길이는 len(prices) - 1 이다.
        """
        return tuple(
            LogReturn.from_prices(prev_price, curr_price)
            for (_, prev_price), (_, curr_price) in zip(self.prices, self.prices[1:])
        )

    def latest_date(self) -> date:
        """시계열의 가장 최근 날짜를 반환한다."""
        return self.prices[-1][0]

    def is_sufficient(self, min_obs: int = _DEFAULT_MIN_OBS) -> bool:
        """시계열이 통계 분석에 충분한 관측값을 보유하는지 판단한다.

        WHY: 252 미만의 시계열은 유사도/공적분 추정 시 분산이 커서
             신뢰할 수 없는 신호를 생성한다(ADR-002 참조).
        """
        return len(self.prices) >= min_obs
