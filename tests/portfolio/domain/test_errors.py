"""portfolio 도메인 예외 계층 단위 테스트.

WHY: WeightSumError/ConstraintViolation 이 ValueError 서브클래스로
     일관된 분기 처리가 가능한지 계약을 명시한다.
"""
from __future__ import annotations

import pytest

from portfolio.domain.errors import ConstraintViolation, WeightSumError


class Test_도메인_예외_계층:
    def test_WeightSumError_는_ValueError_서브클래스(self) -> None:
        assert issubclass(WeightSumError, ValueError)

    def test_ConstraintViolation_은_ValueError_서브클래스(self) -> None:
        assert issubclass(ConstraintViolation, ValueError)

    def test_WeightSumError_는_메시지와_함께_raise_가능(self) -> None:
        with pytest.raises(ValueError, match="합계 위반"):
            raise WeightSumError("합계 위반")

    def test_ConstraintViolation_은_메시지와_함께_raise_가능(self) -> None:
        with pytest.raises(ValueError, match="제약 위반"):
            raise ConstraintViolation("제약 위반")
