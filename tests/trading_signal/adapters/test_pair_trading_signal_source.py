"""
PairTradingSignalSource 어댑터 단위/통합 테스트.

WHY: SignalSource Protocol 준수 여부와 어댑터 조립(페어 누락·정렬 등)을
     검증해 유스케이스와의 연결이 올바른지 보장한다.
"""
from datetime import datetime, timedelta

import pytest

from trading_signal.adapters.outbound.pair_trading_signal_source import PairTradingSignalSource
from trading_signal.application.ports.signal_source import SignalSource
from trading_signal.application.use_cases.generate_pair_signals import PairSignalConfig
from trading_signal.domain.pair import Pair
from trading_signal.domain.side import Side

_BASE_TIME = datetime(2024, 1, 1, 9, 0, 0)


def _make_timestamps(n: int) -> list[datetime]:
    return [_BASE_TIME + timedelta(days=i) for i in range(n)]


class TestProtocolConformance:
    """SignalSource Protocol 준수 검증."""

    def test_isinstance_검사_통과(self):
        """PairTradingSignalSource 는 SignalSource Protocol 을 충족한다."""
        adapter = PairTradingSignalSource(
            pairs=[Pair("AAPL", "MSFT")],
            timestamps=_make_timestamps(10),
        )
        assert isinstance(adapter, SignalSource)

    def test_generate_메서드_존재(self):
        adapter = PairTradingSignalSource(pairs=[], timestamps=[])
        assert callable(adapter.generate)


class TestPairTradingSignalSourceAssembly:
    """어댑터 조립 및 위임 검증."""

    def test_price_map_에_없는_페어는_건너뜀(self):
        """price_map 에 종목이 없으면 빈 리스트를 반환한다."""
        adapter = PairTradingSignalSource(
            pairs=[Pair("AAPL", "MSFT")],
            timestamps=_make_timestamps(10),
        )
        # MSFT 누락
        result = adapter.generate({"AAPL": [100.0] * 10})
        assert result == []

    def test_빈_페어_목록은_빈_리스트_반환(self):
        adapter = PairTradingSignalSource(pairs=[], timestamps=_make_timestamps(5))
        result = adapter.generate({"AAPL": [100.0] * 5, "MSFT": [100.0] * 5})
        assert result == []

    def test_기본_설정이_적용된다(self):
        """config=None 으로 생성 시 기본 파라미터가 적용된다."""
        adapter = PairTradingSignalSource(
            pairs=[Pair("AAPL", "MSFT")],
            timestamps=_make_timestamps(5),
        )
        # lookback_window=20 이 기본값이므로 5개 데이터는 신호 없음
        result = adapter.generate({"AAPL": [100.0] * 5, "MSFT": [100.0] * 5})
        assert result == []

    def test_커스텀_config_적용(self):
        """명시적으로 전달한 config 가 유스케이스에 위임된다."""
        config = PairSignalConfig(
            entry_threshold=1.5,
            exit_threshold=0.5,
            lookback_window=5,
        )
        pair = Pair("AAPL", "MSFT")
        n = 10
        price_a = [100.0] * 5 + [120.0] * 5
        price_b = [100.0] * 10
        timestamps = _make_timestamps(n)

        adapter = PairTradingSignalSource(
            pairs=[pair],
            timestamps=timestamps,
            config=config,
        )
        result = adapter.generate({"AAPL": price_a, "MSFT": price_b})

        assert len(result) > 0

    def test_여러_페어_결과는_타임스탬프_오름차순(self):
        """여러 페어의 신호가 타임스탬프 오름차순으로 정렬된다."""
        config = PairSignalConfig(
            entry_threshold=1.5,
            exit_threshold=0.5,
            lookback_window=5,
        )
        n = 10
        timestamps = _make_timestamps(n)
        price_base = [100.0] * n
        price_high = [100.0] * 5 + [120.0] * 5

        adapter = PairTradingSignalSource(
            pairs=[Pair("AAPL", "MSFT"), Pair("AAPL", "GOOG")],
            timestamps=timestamps,
            config=config,
        )
        result = adapter.generate({
            "AAPL": price_high,
            "MSFT": price_base,
            "GOOG": price_base,
        })

        for i in range(len(result) - 1):
            assert result[i].timestamp <= result[i + 1].timestamp


class TestPairTradingSignalSourceE2E:
    """간단한 End-to-End 검증."""

    def test_mean_reverting_페어에서_entry_exit_사이클(self):
        """이탈 → 복귀 패턴에서 SHORT 진입 후 EXIT 신호가 생성된다."""
        config = PairSignalConfig(
            entry_threshold=1.5,
            exit_threshold=0.5,
            lookback_window=5,
        )
        # 초반 5개: 스프레드 0 (기준), 3개: 크게 양수 (SHORT 진입), 5개: 다시 0 (EXIT)
        price_a = [100.0] * 5 + [120.0] * 3 + [100.0] * 5
        price_b = [100.0] * 13
        timestamps = _make_timestamps(13)

        adapter = PairTradingSignalSource(
            pairs=[Pair("AAPL", "MSFT")],
            timestamps=timestamps,
            config=config,
        )
        signals = adapter.generate({"AAPL": price_a, "MSFT": price_b})

        sides = [s.side for s in signals]
        assert Side.SHORT in sides
        assert Side.EXIT in sides
        # EXIT 는 SHORT 이후에 발생해야 한다
        short_idx = next(i for i, s in enumerate(signals) if s.side == Side.SHORT)
        exit_idx = next(i for i, s in enumerate(signals) if s.side == Side.EXIT)
        assert short_idx < exit_idx
