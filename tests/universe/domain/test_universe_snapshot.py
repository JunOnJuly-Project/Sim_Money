"""
UniverseSnapshot 애그리거트 단위 테스트 (TDD RED 단계).

WHY: UniverseSnapshot 은 유니버스 도메인의 핵심 불변 객체로,
     잘못된 상태(빈 종목, 중복, 빈 이름)와 날짜 불일치 union 을
     타입 수준에서 방어해야 한다.
"""
from __future__ import annotations

import pytest
from datetime import date

from market_data.domain.market import Market
from market_data.domain.ticker import Ticker
from universe.domain.universe_snapshot import UniverseSnapshot

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------

KRX_SAMSUNG = Ticker(market=Market.KRX, symbol="005930")
KRX_SK_HYNIX = Ticker(market=Market.KRX, symbol="000660")
KRX_KAKAO = Ticker(market=Market.KRX, symbol="035720")

AS_OF = date(2024, 1, 2)
AS_OF_OTHER = date(2024, 1, 3)


# ---------------------------------------------------------------------------
# 정상 생성
# ---------------------------------------------------------------------------


def test_정상적인_파라미터로_UniverseSnapshot_을_생성한다():
    """이름·날짜·tickers 가 유효하면 예외 없이 생성되어야 한다."""
    snap = UniverseSnapshot(
        name="KOSPI200",
        as_of=AS_OF,
        tickers=(KRX_SAMSUNG, KRX_SK_HYNIX),
    )
    assert snap.name == "KOSPI200"
    assert snap.as_of == AS_OF


# ---------------------------------------------------------------------------
# 불변식 위반 — ValueError
# ---------------------------------------------------------------------------


def test_빈_tickers_로_생성하면_ValueError_를_던진다():
    """종목이 하나도 없는 유니버스는 의미가 없으므로 거부한다."""
    with pytest.raises(ValueError, match="tickers"):
        UniverseSnapshot(name="KOSPI200", as_of=AS_OF, tickers=())


def test_중복_ticker_로_생성하면_ValueError_를_던진다():
    """동일 종목이 두 번 포함되면 유니버스 정의가 모호해지므로 거부한다."""
    with pytest.raises(ValueError, match="중복"):
        UniverseSnapshot(
            name="KOSPI200",
            as_of=AS_OF,
            tickers=(KRX_SAMSUNG, KRX_SAMSUNG),
        )


def test_공백_name_으로_생성하면_ValueError_를_던진다():
    """이름이 공백이면 유니버스를 식별할 수 없으므로 거부한다."""
    with pytest.raises(ValueError, match="name"):
        UniverseSnapshot(name="   ", as_of=AS_OF, tickers=(KRX_SAMSUNG,))


# ---------------------------------------------------------------------------
# 컬렉션 프로토콜
# ---------------------------------------------------------------------------


def test_len_은_ticker_개수를_반환한다():
    """len(snap) 은 포함된 종목 수를 반환해야 한다."""
    snap = UniverseSnapshot(
        name="KOSPI200",
        as_of=AS_OF,
        tickers=(KRX_SAMSUNG, KRX_SK_HYNIX),
    )
    assert len(snap) == 2


def test_contains_는_포함된_ticker_에_True_를_반환한다():
    """in 연산자로 포함 여부를 확인할 수 있어야 한다."""
    snap = UniverseSnapshot(
        name="KOSPI200",
        as_of=AS_OF,
        tickers=(KRX_SAMSUNG, KRX_SK_HYNIX),
    )
    assert KRX_SAMSUNG in snap
    assert KRX_KAKAO not in snap


def test_iter_는_모든_ticker_를_순회한다():
    """for-loop 로 모든 종목을 순회할 수 있어야 한다."""
    tickers = (KRX_SAMSUNG, KRX_SK_HYNIX)
    snap = UniverseSnapshot(name="KOSPI200", as_of=AS_OF, tickers=tickers)
    assert tuple(snap) == tickers


# ---------------------------------------------------------------------------
# union
# ---------------------------------------------------------------------------


def test_union_은_같은_as_of_의_두_스냅샷을_합친다():
    """같은 날짜의 두 유니버스를 합집합으로 합쳐야 한다.

    - name 은 '{a}+{b}' 형식
    - 중복 종목은 한 번만 포함
    - as_of 는 공통 날짜 유지
    """
    snap_a = UniverseSnapshot(
        name="KOSPI200",
        as_of=AS_OF,
        tickers=(KRX_SAMSUNG, KRX_SK_HYNIX),
    )
    snap_b = UniverseSnapshot(
        name="KOSDAQ150",
        as_of=AS_OF,
        tickers=(KRX_SK_HYNIX, KRX_KAKAO),
    )
    merged = snap_a.union(snap_b)

    assert merged.name == "KOSPI200+KOSDAQ150"
    assert merged.as_of == AS_OF
    assert KRX_SAMSUNG in merged
    assert KRX_SK_HYNIX in merged
    assert KRX_KAKAO in merged
    assert len(merged) == 3


def test_union_은_다른_as_of_의_스냅샷을_거부한다():
    """날짜가 다른 유니버스를 합치면 시점이 달라 의미가 없으므로 거부한다."""
    snap_a = UniverseSnapshot(
        name="KOSPI200",
        as_of=AS_OF,
        tickers=(KRX_SAMSUNG,),
    )
    snap_b = UniverseSnapshot(
        name="KOSDAQ150",
        as_of=AS_OF_OTHER,
        tickers=(KRX_SK_HYNIX,),
    )
    with pytest.raises(ValueError, match="as_of"):
        snap_a.union(snap_b)
