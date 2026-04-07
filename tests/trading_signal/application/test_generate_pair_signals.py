"""
GeneratePairSignals 유스케이스 단위 테스트.

WHY: 페어 트레이딩 핵심 로직(진입/청산/lookback 부족/경계 조건)을
     격리 테스트해 z-score 기반 신호 생성의 정확성을 보장한다.
"""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from trading_signal.application.use_cases.generate_pair_signals import (
    GeneratePairSignals,
    PairSignalConfig,
)
from trading_signal.domain.pair import Pair
from trading_signal.domain.side import Side

_BASE_TIME = datetime(2024, 1, 1, 9, 0, 0)
_CONFIG = PairSignalConfig(
    entry_threshold=1.5,
    exit_threshold=0.5,
    lookback_window=5,
)


def _make_timestamps(n: int) -> list[datetime]:
    """n 개의 연속 타임스탬프를 생성한다."""
    return [_BASE_TIME + timedelta(days=i) for i in range(n)]


def _flat_prices(n: int, value: float = 100.0) -> list[float]:
    """n 개의 동일 가격을 반환한다."""
    return [value] * n


class TestGeneratePairSignalsEntry:
    """진입 신호 생성 검증."""

    def test_양수_이탈_시_a_종목_SHORT_신호(self):
        """spread 가 양수로 크게 벌어지면 a(고평가) 매도 신호."""
        pair = Pair("AAPL", "MSFT")
        # a - b 스프레드: 처음 5개 평균 0, 이후 크게 양수
        price_a = [100.0] * 5 + [120.0] * 5
        price_b = [100.0] * 10
        timestamps = _make_timestamps(10)

        signals = GeneratePairSignals().execute(pair, price_a, price_b, timestamps, _CONFIG)

        assert len(signals) > 0
        entry = signals[0]
        assert entry.side == Side.SHORT
        assert entry.ticker == pair.a

    def test_음수_이탈_시_a_종목_LONG_신호(self):
        """spread 가 음수로 크게 벌어지면 a(저평가) 매수 신호."""
        pair = Pair("AAPL", "MSFT")
        price_a = [100.0] * 5 + [80.0] * 5
        price_b = [100.0] * 10
        timestamps = _make_timestamps(10)

        signals = GeneratePairSignals().execute(pair, price_a, price_b, timestamps, _CONFIG)

        assert len(signals) > 0
        entry = signals[0]
        assert entry.side == Side.LONG
        assert entry.ticker == pair.a

    def test_임계값_미달_시_신호_없음(self):
        """z-score 가 entry_threshold 이내면 신호를 생성하지 않는다."""
        pair = Pair("AAPL", "MSFT")
        # 소폭 변동 (z-score < 2.0 예상)
        price_a = [100.0, 101.0, 100.5, 99.5, 100.2, 100.1, 100.3, 100.0, 99.8, 100.1]
        price_b = [100.0] * 10
        timestamps = _make_timestamps(10)

        config = PairSignalConfig(
            entry_threshold=5.0,  # 매우 높은 임계값
            exit_threshold=0.5,
            lookback_window=5,
        )
        signals = GeneratePairSignals().execute(pair, price_a, price_b, timestamps, config)

        assert all(s.side != Side.SHORT and s.side != Side.LONG for s in signals)


class TestGeneratePairSignalsExit:
    """청산 신호 생성 검증."""

    def test_mean_reverting_패턴에서_진입_후_EXIT_신호(self):
        """spread 이탈 후 복귀 시 EXIT 신호가 생성된다."""
        pair = Pair("AAPL", "MSFT")
        # 초반 정상 → 이탈 → 복귀
        price_a = [100.0] * 5 + [120.0] * 3 + [100.0] * 5
        price_b = [100.0] * 13
        timestamps = _make_timestamps(13)

        signals = GeneratePairSignals().execute(pair, price_a, price_b, timestamps, _CONFIG)

        sides = [s.side for s in signals]
        assert Side.EXIT in sides

    def test_strength_는_0이상_1이하(self):
        """생성된 모든 신호의 strength 불변식 확인."""
        pair = Pair("AAPL", "MSFT")
        price_a = [100.0] * 5 + [125.0] * 5
        price_b = [100.0] * 10
        timestamps = _make_timestamps(10)

        signals = GeneratePairSignals().execute(pair, price_a, price_b, timestamps, _CONFIG)

        for sig in signals:
            assert Decimal("0") <= sig.strength <= Decimal("1")


class TestGeneratePairSignalsLookback:
    """lookback 부족 케이스 검증."""

    def test_lookback_과_동일_길이_데이터는_신호_없음(self):
        """가격 데이터 길이 == lookback_window 이면 신호가 없다."""
        pair = Pair("AAPL", "MSFT")
        price_a = [100.0] * 5
        price_b = [95.0] * 5
        timestamps = _make_timestamps(5)

        config = PairSignalConfig(
            entry_threshold=1.0,
            exit_threshold=0.5,
            lookback_window=5,
        )
        signals = GeneratePairSignals().execute(pair, price_a, price_b, timestamps, config)

        assert signals == []

    def test_빈_가격_데이터는_신호_없음(self):
        """빈 가격 시계열은 신호를 생성하지 않는다."""
        pair = Pair("AAPL", "MSFT")
        signals = GeneratePairSignals().execute(pair, [], [], [], _CONFIG)
        assert signals == []

    def test_표준편차_0인_구간은_zscore_계산_건너뜀(self):
        """완전히 평탄한 스프레드 구간은 신호를 생성하지 않는다."""
        pair = Pair("AAPL", "MSFT")
        # 동일한 스프레드가 지속되면 stdev=0
        price_a = [105.0] * 20
        price_b = [100.0] * 20
        timestamps = _make_timestamps(20)

        signals = GeneratePairSignals().execute(pair, price_a, price_b, timestamps, _CONFIG)

        assert signals == []
