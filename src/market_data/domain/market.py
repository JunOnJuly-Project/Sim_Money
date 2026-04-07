"""
시장 열거형.

WHY: 거래소마다 종목 코드 체계와 거래 시간이 다르므로
     시장을 타입 수준에서 구분해 잘못된 혼용을 방지한다.
"""
from enum import Enum


class Market(str, Enum):
    """지원하는 거래소 목록."""

    KRX = "KRX"
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"
