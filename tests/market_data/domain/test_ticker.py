"""
Ticker 값 객체 단위 테스트.

WHY: Ticker 는 시스템 전반의 종목 식별자 역할을 하므로
     잘못된 생성을 방어하고 불변성을 보장해야 한다.
"""
import pytest
from market_data.domain.ticker import Ticker
from market_data.domain.market import Market


def test_Ticker_는_공백_심볼을_거부한다():
    """공백만 있는 심볼은 유효하지 않은 종목 코드다."""
    with pytest.raises(ValueError):
        Ticker(market=Market.KRX, symbol="   ")


def test_Ticker_는_빈_심볼을_거부한다():
    """빈 문자열은 유효하지 않은 종목 코드다."""
    with pytest.raises(ValueError):
        Ticker(market=Market.KRX, symbol="")


def test_Ticker_는_대소문자_정규화한다():
    """NASDAQ/NYSE 심볼은 대문자로 정규화되어야 한다."""
    t = Ticker(market=Market.NASDAQ, symbol="aapl")
    assert t.symbol == "AAPL"


def test_Ticker_는_KRX_심볼_대문자_유지():
    """KRX 숫자 코드는 대문자 정규화 후에도 그대로여야 한다."""
    t = Ticker(market=Market.KRX, symbol="005930")
    assert t.symbol == "005930"


def test_Ticker_from_string_은_시장과_심볼을_파싱한다():
    """'KRX:005930' 형식 문자열을 Ticker 로 파싱한다."""
    t = Ticker.from_string("KRX:005930")
    assert t.market == Market.KRX
    assert t.symbol == "005930"


def test_Ticker_str_은_복원_가능하다():
    """str(ticker) 로 from_string 에 전달 가능한 문자열을 복원한다."""
    t = Ticker(market=Market.NASDAQ, symbol="AAPL")
    assert str(t) == "NASDAQ:AAPL"


def test_Ticker_는_해시_가능하다():
    """동일 시장·심볼의 Ticker 는 같은 해시값을 가져야 한다."""
    t1 = Ticker(market=Market.KRX, symbol="005930")
    t2 = Ticker(market=Market.KRX, symbol="005930")
    assert hash(t1) == hash(t2)
    assert {t1, t2} == {t1}
