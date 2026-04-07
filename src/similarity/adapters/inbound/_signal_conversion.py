"""
TradingSignal → backtest Signal 변환 유틸.

WHY: trading_signal 도메인과 backtest 도메인은 L3↔L3 직접 결합을 피해야 한다.
     인바운드 어댑터(조립 루트)가 두 L3 모듈을 조립하므로 이 변환 함수가
     어댑터 레이어에 위치하는 것이 적절하다.
     Side enum 의 value 문자열이 동일("LONG"/"SHORT"/"EXIT")하므로
     1:1 매핑이 보장된다.
"""
from __future__ import annotations

from backtest.domain.signal import Signal
from backtest.domain.signal import Side as BacktestSide
from trading_signal.domain.trading_signal import TradingSignal


def trading_signal_to_backtest_signal(ts: TradingSignal) -> Signal:
    """TradingSignal 을 backtest.domain.Signal 로 변환한다.

    WHY: 두 도메인의 Side enum 은 독립적으로 선언되어 있으나
         value 문자열이 동일하므로 value 경유 변환이 안전하다.

    Args:
        ts: trading_signal 도메인의 신호 값 객체

    Returns:
        backtest 도메인의 Signal 값 객체
    """
    backtest_side = BacktestSide(ts.side.value)
    return Signal(
        timestamp=ts.timestamp,
        ticker=ts.ticker,
        side=backtest_side,
        strength=ts.strength,
    )
