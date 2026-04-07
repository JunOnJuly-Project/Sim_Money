"""
backtest 애플리케이션 포트 Protocol 단위 테스트 (TDD RED 단계).

WHY: L3 클린 아키텍처에서 포트는 의존성 역전(DIP)의 핵심이다.
     @runtime_checkable Protocol 로 선언하면 어댑터가 인터페이스를
     정적·동적으로 모두 준수하는지 검증할 수 있다.
     구현 전에 Protocol 계약을 테스트로 고정해 어댑터 오류를 조기에 발견한다.
"""
from __future__ import annotations

import pytest

# WHY: 아직 미구현 상태이므로 import 자체가 RED 의 시작점이다.
from backtest.application.ports.backtest_engine import BacktestEngine
from backtest.application.ports.signal_source import SignalSource
from backtest.application.ports.trade_executor import TradeExecutor
from backtest.application.ports.performance_calculator import PerformanceCalculator


# ─────────────────────────────────────────────
# 더미 구현 클래스 (isinstance 검증용)
# WHY: Protocol 은 구조적 서브타이핑이므로 명시적 상속 없이도
#      필요한 메서드만 갖추면 isinstance 가 True 를 반환해야 한다.
# ─────────────────────────────────────────────

class _DummyBacktestEngine:
    """BacktestEngine Protocol 을 만족하는 최소 더미."""
    def run(self, signals, price_history):
        ...


class _DummySignalSource:
    """SignalSource Protocol 을 만족하는 최소 더미."""
    def generate(self, price_history):
        ...


class _DummyTradeExecutor:
    """TradeExecutor Protocol 을 만족하는 최소 더미."""
    def execute(self, signal, position):
        ...


class _DummyPerformanceCalculator:
    """PerformanceCalculator Protocol 을 만족하는 최소 더미."""
    def compute(self, trades, equity_curve):
        ...


# ─────────────────────────────────────────────
# 메서드 불충족 더미 (isinstance False 검증용)
# ─────────────────────────────────────────────

class _NonConformingClass:
    """아무 메서드도 갖지 않는 클래스 — Protocol 미충족."""
    pass


# ═════════════════════════════════════════════
# BacktestEngine Protocol
# ═════════════════════════════════════════════
class TestBacktestEngine_Protocol:
    def test_run_메서드를_가진_클래스는_BacktestEngine_isinstance를_통과한다(self):
        """WHY: run(signals, price_history) 시그니처를 갖추면 어댑터로 인정해야 한다."""
        assert isinstance(_DummyBacktestEngine(), BacktestEngine)

    def test_메서드_없는_클래스는_BacktestEngine_isinstance를_실패한다(self):
        """WHY: Protocol 계약 미충족 클래스는 isinstance 에서 False 를 반환해야 한다."""
        assert not isinstance(_NonConformingClass(), BacktestEngine)

    def test_BacktestEngine은_runtime_checkable_Protocol이다(self):
        """WHY: @runtime_checkable 없이는 isinstance 검사 자체가 TypeError 를 던진다."""
        # runtime_checkable 이면 TypeError 없이 isinstance 가 동작한다
        try:
            isinstance(object(), BacktestEngine)
        except TypeError:
            pytest.fail("BacktestEngine 이 @runtime_checkable 이 아닙니다")


# ═════════════════════════════════════════════
# SignalSource Protocol
# ═════════════════════════════════════════════
class TestSignalSource_Protocol:
    def test_generate_메서드를_가진_클래스는_SignalSource_isinstance를_통과한다(self):
        """WHY: generate(price_history) 시그니처를 갖추면 신호 생성기로 인정해야 한다."""
        assert isinstance(_DummySignalSource(), SignalSource)

    def test_메서드_없는_클래스는_SignalSource_isinstance를_실패한다(self):
        """WHY: generate 가 없으면 신호 생성 계약을 이행할 수 없다."""
        assert not isinstance(_NonConformingClass(), SignalSource)

    def test_SignalSource는_runtime_checkable_Protocol이다(self):
        """WHY: 동적 isinstance 검증을 위해 @runtime_checkable 이 필수다."""
        try:
            isinstance(object(), SignalSource)
        except TypeError:
            pytest.fail("SignalSource 가 @runtime_checkable 이 아닙니다")


# ═════════════════════════════════════════════
# TradeExecutor Protocol
# ═════════════════════════════════════════════
class TestTradeExecutor_Protocol:
    def test_execute_메서드를_가진_클래스는_TradeExecutor_isinstance를_통과한다(self):
        """WHY: execute(signal, position) 시그니처를 갖추면 주문 실행기로 인정해야 한다."""
        assert isinstance(_DummyTradeExecutor(), TradeExecutor)

    def test_메서드_없는_클래스는_TradeExecutor_isinstance를_실패한다(self):
        """WHY: execute 가 없으면 주문 실행 계약을 이행할 수 없다."""
        assert not isinstance(_NonConformingClass(), TradeExecutor)

    def test_TradeExecutor는_runtime_checkable_Protocol이다(self):
        """WHY: 동적 isinstance 검증을 위해 @runtime_checkable 이 필수다."""
        try:
            isinstance(object(), TradeExecutor)
        except TypeError:
            pytest.fail("TradeExecutor 가 @runtime_checkable 이 아닙니다")


# ═════════════════════════════════════════════
# PerformanceCalculator Protocol
# ═════════════════════════════════════════════
class TestPerformanceCalculator_Protocol:
    def test_compute_메서드를_가진_클래스는_PerformanceCalculator_isinstance를_통과한다(self):
        """WHY: compute(trades, equity_curve) 시그니처를 갖추면 성과 계산기로 인정해야 한다."""
        assert isinstance(_DummyPerformanceCalculator(), PerformanceCalculator)

    def test_메서드_없는_클래스는_PerformanceCalculator_isinstance를_실패한다(self):
        """WHY: compute 가 없으면 성과 집계 계약을 이행할 수 없다."""
        assert not isinstance(_NonConformingClass(), PerformanceCalculator)

    def test_PerformanceCalculator는_runtime_checkable_Protocol이다(self):
        """WHY: 동적 isinstance 검증을 위해 @runtime_checkable 이 필수다."""
        try:
            isinstance(object(), PerformanceCalculator)
        except TypeError:
            pytest.fail("PerformanceCalculator 가 @runtime_checkable 이 아닙니다")
