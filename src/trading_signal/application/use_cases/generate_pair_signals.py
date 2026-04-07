"""
GeneratePairSignals 유스케이스.

WHY: 페어 트레이딩 신호 생성 로직을 단일 유스케이스로 캡슐화해
     어댑터(PairTradingSignalSource)가 조합만 담당하도록 한다.
     beta=1 단순화(M2 범위)를 WHY 주석으로 명시해 Phase 3+ 에서
     OLS 회귀 beta 도입 시 변경 범위를 명확히 한다.

     z-score 계산에 stdlib math/statistics 만 사용해 domain purity 를 지킨다.
     pandas/numpy 는 애플리케이션 레이어에서도 금지(import-linter 계약).
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from trading_signal.domain.pair import Pair
from trading_signal.domain.side import Side
from trading_signal.domain.trading_signal import TradingSignal
from trading_signal.domain.zscore import ZScore

# WHY: lookback_window 최소값 — 평균·표준편차가 의미를 갖는 최소 표본 수
_MIN_LOOKBACK: int = 2


@dataclass
class PairSignalConfig:
    """페어 신호 생성 파라미터 묶음 DTO.

    WHY: 매개변수 3개 초과 방지 및 설정 변경 시 호출부를 수정하지 않도록 한다.
    """

    entry_threshold: float
    exit_threshold: float
    lookback_window: int


class GeneratePairSignals:
    """페어 트레이딩 신호 생성 유스케이스.

    스프레드 = price_a - price_b (beta=1 M2 단순화).
    rolling z-score 를 계산해 entry_threshold 초과 시 진입,
    exit_threshold 미만 시 청산 신호를 생성한다.
    """

    def execute(
        self,
        pair: Pair,
        price_a: Sequence[float],
        price_b: Sequence[float],
        timestamps: Sequence[datetime],
        config: PairSignalConfig,
    ) -> list[TradingSignal]:
        """페어 가격 시계열에서 TradingSignal 목록을 생성한다.

        Args:
            pair: 페어 종목 쌍
            price_a: 종목 a 종가 시계열
            price_b: 종목 b 종가 시계열
            timestamps: 각 가격에 대응하는 타임스탬프
            config: 진입/청산 임계값 및 lookback 설정

        Returns:
            생성된 TradingSignal 목록 (lookback 부족 시 빈 리스트)
        """
        spreads = self._calc_spreads(price_a, price_b)
        return self._scan_signals(pair, spreads, timestamps, config)

    def _calc_spreads(
        self,
        price_a: Sequence[float],
        price_b: Sequence[float],
    ) -> list[float]:
        """스프레드 시계열 계산 (beta=1 단순화)."""
        return [a - b for a, b in zip(price_a, price_b)]

    def _scan_signals(
        self,
        pair: Pair,
        spreads: list[float],
        timestamps: Sequence[datetime],
        config: PairSignalConfig,
    ) -> list[TradingSignal]:
        """rolling z-score 스캔으로 신호를 추출한다."""
        signals: list[TradingSignal] = []
        in_position = False

        for i in range(config.lookback_window, len(spreads)):
            window = spreads[i - config.lookback_window : i]
            zscore = self._calc_zscore(window)
            if zscore is None:
                continue

            signal = self._decide_signal(
                pair, timestamps[i], zscore, config, in_position
            )
            if signal is not None:
                signals.append(signal)
                in_position = signal.side != Side.EXIT

        return signals

    def _calc_zscore(self, window: list[float]) -> ZScore | None:
        """window 의 z-score 를 계산한다. 표준편차 0 이면 None 반환."""
        if len(window) < _MIN_LOOKBACK:
            return None
        mean = statistics.mean(window)
        stdev = statistics.stdev(window)
        if stdev == 0.0 or math.isnan(stdev):
            return None
        return ZScore((window[-1] - mean) / stdev)

    def _decide_signal(
        self,
        pair: Pair,
        timestamp: datetime,
        zscore: ZScore,
        config: PairSignalConfig,
        in_position: bool,
    ) -> TradingSignal | None:
        """z-score 와 포지션 상태에 따라 신호를 결정한다."""
        z = zscore.value
        strength = Decimal(str(min(abs(z) / config.entry_threshold, 1.0)))

        if not in_position:
            return self._entry_signal(pair, timestamp, z, config, strength)
        return self._exit_signal(pair, timestamp, z, config)

    def _entry_signal(
        self,
        pair: Pair,
        timestamp: datetime,
        z: float,
        config: PairSignalConfig,
        strength: Decimal,
    ) -> TradingSignal | None:
        """진입 조건 충족 시 신호를 생성한다."""
        if z > config.entry_threshold:
            # WHY: spread 가 양으로 크게 이탈 → a 매도/b 매수 (a 고평가)
            return TradingSignal(timestamp, pair.a, Side.SHORT, strength)
        if z < -config.entry_threshold:
            # WHY: spread 가 음으로 크게 이탈 → a 매수/b 매도 (a 저평가)
            return TradingSignal(timestamp, pair.a, Side.LONG, strength)
        return None

    def _exit_signal(
        self,
        pair: Pair,
        timestamp: datetime,
        z: float,
        config: PairSignalConfig,
    ) -> TradingSignal | None:
        """청산 조건 충족 시 EXIT 신호를 생성한다."""
        if abs(z) < config.exit_threshold:
            return TradingSignal(
                timestamp, pair.a, Side.EXIT, Decimal("1")
            )
        return None
