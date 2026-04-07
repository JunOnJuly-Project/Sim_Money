"""
portfolio 도메인 예외 계층.

WHY: 도메인 규칙 위반을 ValueError 서브클래스로 표현해 호출자가
     일반 ValueError 와 동일하게 처리하거나 세밀하게 분기할 수 있게 한다.
"""
from __future__ import annotations


class WeightSumError(ValueError):
    """가중치 합이 허용 범위를 벗어났을 때 발생한다."""


class ConstraintViolation(ValueError):
    """포트폴리오 제약 조건 위반 시 발생한다."""
