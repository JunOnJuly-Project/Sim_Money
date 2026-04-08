"""risk 도메인 예외.

WHY: 값 객체 불변식 위반을 표준 ValueError 와 구분하기 위해 도메인 고유 예외를 정의한다.
"""


class RiskDomainError(ValueError):
    """risk 도메인 값 객체 불변식 위반."""
