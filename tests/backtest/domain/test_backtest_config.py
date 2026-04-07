"""
BacktestConfig 값 객체 단위 테스트.

WHY: 경제적 불변식(양수 자본, 비음수 비용)이 생성 시점에 검증되는지 확인해
     잘못된 파라미터로 백테스트가 시작되는 상황을 사전에 차단한다.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from backtest.domain.backtest_config import BacktestConfig


class TestBacktestConfigValid:
    """정상 생성 케이스."""

    def test_기본_필드만으로_생성된다(self) -> None:
        config = BacktestConfig(
            initial_capital=Decimal("1000000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("5"),
        )
        assert config.initial_capital == Decimal("1000000")
        assert config.fee_rate == Decimal("0.001")
        assert config.slippage_bps == Decimal("5")
        assert config.start is None
        assert config.end is None

    def test_기간이_포함된_설정을_생성한다(self) -> None:
        start = datetime(2023, 1, 1)
        end = datetime(2023, 12, 31)
        config = BacktestConfig(
            initial_capital=Decimal("500000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
            start=start,
            end=end,
        )
        assert config.start == start
        assert config.end == end

    def test_수수료와_슬리피지가_0이어도_생성된다(self) -> None:
        config = BacktestConfig(
            initial_capital=Decimal("1"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
        )
        assert config.fee_rate == Decimal("0")
        assert config.slippage_bps == Decimal("0")

    def test_frozen_이므로_필드_수정이_불가하다(self) -> None:
        config = BacktestConfig(
            initial_capital=Decimal("1000000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("5"),
        )
        with pytest.raises(Exception):
            config.initial_capital = Decimal("9999")  # type: ignore[misc]


class TestBacktestConfigInvalid:
    """불변식 위반 케이스."""

    def test_initial_capital이_0이면_예외가_발생한다(self) -> None:
        with pytest.raises(ValueError, match="initial_capital"):
            BacktestConfig(
                initial_capital=Decimal("0"),
                fee_rate=Decimal("0.001"),
                slippage_bps=Decimal("5"),
            )

    def test_initial_capital이_음수이면_예외가_발생한다(self) -> None:
        with pytest.raises(ValueError, match="initial_capital"):
            BacktestConfig(
                initial_capital=Decimal("-1"),
                fee_rate=Decimal("0.001"),
                slippage_bps=Decimal("5"),
            )

    def test_fee_rate가_음수이면_예외가_발생한다(self) -> None:
        with pytest.raises(ValueError, match="fee_rate"):
            BacktestConfig(
                initial_capital=Decimal("1000000"),
                fee_rate=Decimal("-0.001"),
                slippage_bps=Decimal("5"),
            )

    def test_slippage_bps가_음수이면_예외가_발생한다(self) -> None:
        with pytest.raises(ValueError, match="slippage_bps"):
            BacktestConfig(
                initial_capital=Decimal("1000000"),
                fee_rate=Decimal("0.001"),
                slippage_bps=Decimal("-1"),
            )
