"""
market_data 도메인 공통 예외 계층.

WHY: 도메인 예외를 인프라 예외와 분리함으로써
     상위 레이어가 특정 기술 스택에 의존하지 않도록 한다.
"""


class DomainError(Exception):
    """market_data 도메인 공통 예외."""


class StaleDataError(DomainError):
    """전처리 게이트(N<252, σ<ε, NaN>5% 등)를 통과하지 못한 경우."""
