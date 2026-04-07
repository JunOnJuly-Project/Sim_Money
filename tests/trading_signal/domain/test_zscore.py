"""
ZScore 값 객체 단위 테스트.

WHY: 단순 래퍼 VO 의 값 저장·비교·불변성을 검증해
     호출부가 타입 안전하게 z-score 를 전달할 수 있음을 보장한다.
"""
import pytest

from trading_signal.domain.zscore import ZScore


class TestZScoreValue:
    """ZScore 값 저장 및 비교 검증."""

    def test_양수_zscore_저장(self):
        z = ZScore(2.5)
        assert z.value == 2.5

    def test_음수_zscore_저장(self):
        z = ZScore(-1.8)
        assert z.value == -1.8

    def test_영_zscore_저장(self):
        z = ZScore(0.0)
        assert z.value == 0.0

    def test_동일_값은_동등하다(self):
        assert ZScore(2.0) == ZScore(2.0)

    def test_다른_값은_동등하지_않다(self):
        assert ZScore(2.0) != ZScore(1.5)

    def test_frozen_객체는_필드_변경_불가(self):
        z = ZScore(1.5)
        with pytest.raises(Exception):
            z.value = 3.0  # type: ignore[misc]
