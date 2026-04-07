"""
매매 방향 열거형.

WHY: signal 모듈이 backtest.domain.Side 를 import 하면 L3↔L3 간 결합이 생겨
     독립 배포 단위 경계가 흐려진다. signal 도메인 전용으로 자체 Side 를 선언해
     두 L3 모듈이 서로를 몰라도 되도록 한다.
"""
from __future__ import annotations

from enum import Enum


class Side(Enum):
    """매매 방향 — 매수(LONG), 매도(SHORT), 청산(EXIT) 세 가지만 허용."""

    LONG = "LONG"
    SHORT = "SHORT"
    EXIT = "EXIT"
