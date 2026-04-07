"""
PairTradingSignalSource 아웃바운드 어댑터.

WHY: SignalSource Protocol 을 구현하는 구체 어댑터.
     price_map 을 받아 등록된 페어 목록에 대해 GeneratePairSignals 유스케이스를
     순서대로 호출하고 결과를 합산한다.
     타임스탬프는 price_map 과 독립적으로 주입받아
     도메인이 datetime 생성에 관여하지 않도록 격리한다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence

from trading_signal.application.use_cases.generate_pair_signals import (
    GeneratePairSignals,
    PairSignalConfig,
)
from trading_signal.domain.pair import Pair
from trading_signal.domain.trading_signal import TradingSignal

# 기본 파라미터 상수
_DEFAULT_ENTRY_THRESHOLD: float = 2.0
_DEFAULT_EXIT_THRESHOLD: float = 0.5
_DEFAULT_LOOKBACK_WINDOW: int = 20


class PairTradingSignalSource:
    """페어 트레이딩 신호 생성 아웃바운드 어댑터.

    SignalSource Protocol 을 구조적 서브타이핑으로 충족한다.
    """

    def __init__(
        self,
        pairs: list[Pair],
        timestamps: list[datetime],
        config: PairSignalConfig | None = None,
    ) -> None:
        """어댑터를 초기화한다.

        Args:
            pairs: 신호를 생성할 페어 목록
            timestamps: 가격 시계열에 대응하는 타임스탬프 목록
            config: 신호 생성 파라미터 (None 이면 기본값 사용)
        """
        self._pairs = pairs
        self._timestamps = timestamps
        self._config = config or PairSignalConfig(
            entry_threshold=_DEFAULT_ENTRY_THRESHOLD,
            exit_threshold=_DEFAULT_EXIT_THRESHOLD,
            lookback_window=_DEFAULT_LOOKBACK_WINDOW,
        )
        self._use_case = GeneratePairSignals()

    def generate(
        self,
        price_map: Mapping[str, Sequence[float]],
    ) -> list[TradingSignal]:
        """등록된 모든 페어에 대해 신호를 생성한다.

        Args:
            price_map: 종목코드 → 종가 시계열 매핑

        Returns:
            생성된 TradingSignal 목록 (타임스탬프 오름차순)
        """
        all_signals: list[TradingSignal] = []
        for pair in self._pairs:
            signals = self._generate_for_pair(pair, price_map)
            all_signals.extend(signals)
        return sorted(all_signals, key=lambda s: s.timestamp)

    def _generate_for_pair(
        self,
        pair: Pair,
        price_map: Mapping[str, Sequence[float]],
    ) -> list[TradingSignal]:
        """단일 페어에 대해 신호를 생성한다. 가격 데이터 없으면 빈 리스트."""
        if pair.a not in price_map or pair.b not in price_map:
            return []
        return self._use_case.execute(
            pair=pair,
            price_a=price_map[pair.a],
            price_b=price_map[pair.b],
            timestamps=self._timestamps,
            config=self._config,
        )
