"""
Pair 값 객체 단위 테스트.

WHY: frozen 불변 객체의 정규화·불변식을 테스트해
     호출부가 순서를 바꿔도 동일한 페어가 생성됨을 보장한다.
"""
import pytest

from trading_signal.domain.pair import Pair


class TestPairNormalization:
    """정규화(a < b 정렬) 검증."""

    def test_이미_정렬된_페어는_그대로_저장된다(self):
        pair = Pair("AAPL", "MSFT")
        assert pair.a == "AAPL"
        assert pair.b == "MSFT"

    def test_역순_입력은_알파벳_순으로_정규화된다(self):
        pair = Pair("MSFT", "AAPL")
        assert pair.a == "AAPL"
        assert pair.b == "MSFT"

    def test_정규화된_페어는_순서_무관하게_동등하다(self):
        forward = Pair("AAPL", "MSFT")
        reversed_ = Pair("MSFT", "AAPL")
        assert forward == reversed_

    def test_정규화된_페어는_동일_해시를_갖는다(self):
        forward = Pair("AAPL", "MSFT")
        reversed_ = Pair("MSFT", "AAPL")
        assert hash(forward) == hash(reversed_)


class TestPairInvariants:
    """불변식 위반 시 ValueError 검증."""

    def test_자기_자신과_페어_구성_시_에러(self):
        with pytest.raises(ValueError, match="자기 자신"):
            Pair("AAPL", "AAPL")

    def test_빈_문자열_a_는_에러(self):
        with pytest.raises(ValueError, match="빈 문자열"):
            Pair("", "AAPL")

    def test_빈_문자열_b_는_에러(self):
        with pytest.raises(ValueError, match="빈 문자열"):
            Pair("AAPL", "")

    def test_frozen_페어는_필드_변경_불가(self):
        pair = Pair("AAPL", "MSFT")
        with pytest.raises(Exception):
            pair.a = "GOOG"  # type: ignore[misc]
