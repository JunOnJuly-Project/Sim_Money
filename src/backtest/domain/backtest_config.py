"""
백테스트 실행 설정 값 객체.

WHY: 백테스트 파라미터(초기 자본, 수수료, 슬리피지, 기간)는 실행 도중 변경되면
     결과 재현성이 깨진다. frozen dataclass 로 불변성을 보장하고
     생성 시점에 경제적 불변식(양수 자본, 비음수 비용)을 검증해
     잘못된 파라미터로 시뮬레이션이 시작되는 것을 방지한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

_MIN_CAPITAL = Decimal("0")
_MIN_FEE_RATE = Decimal("0")
_MIN_SLIPPAGE_BPS = Decimal("0")


@dataclass(frozen=True)
class BacktestConfig:
    """백테스트 실행 환경 설정 값 객체."""

    initial_capital: Decimal
    fee_rate: Decimal
    slippage_bps: Decimal
    start: datetime | None = None
    end: datetime | None = None

    def __post_init__(self) -> None:
        """경제적 불변식 검증."""
        if self.initial_capital <= _MIN_CAPITAL:
            raise ValueError("initial_capital 은 0 초과이어야 합니다.")
        if self.fee_rate < _MIN_FEE_RATE:
            raise ValueError("fee_rate 는 0 이상이어야 합니다.")
        if self.slippage_bps < _MIN_SLIPPAGE_BPS:
            raise ValueError("slippage_bps 는 0 이상이어야 합니다.")
