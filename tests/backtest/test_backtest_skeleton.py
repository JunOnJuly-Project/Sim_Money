"""
InMemoryBacktestEngine 어댑터 스켈레톤 테스트 (TDD RED 단계).

WHY: M2 S3 에서는 어댑터 파일 존재 여부와 NotImplementedError 계약만
     검증한다. 실제 실행 로직은 M2 S4 에서 구현될 예정이다.
     스텁 메서드가 "M2 S4" 를 메시지에 포함해야 다음 마일스톤 담당자가
     어떤 슬라이스에서 구현해야 하는지 즉시 파악할 수 있다.
"""
from __future__ import annotations

import pytest


class TestInMemoryBacktestEngine_임포트:
    def test_InMemoryBacktestEngine을_임포트할_수_있다(self):
        """WHY: 어댑터 파일이 존재하지 않으면 CI 전체가 실패한다.
               import 성공 여부로 파일 존재 및 문법 오류를 조기에 감지한다."""
        # WHY: 아직 미구현이므로 ModuleNotFoundError 로 RED 가 된다.
        from backtest.adapters.outbound.in_memory_backtest_engine import (  # noqa: F401
            InMemoryBacktestEngine,
        )

    def test_모듈_임포트는_부작용이_없다(self):
        """WHY: 최상위 임포트 시 네트워크 호출·파일 I/O·전역 변수 초기화 등
               부작용이 있으면 테스트 격리가 깨진다."""
        # 이 테스트는 임포트 자체의 부작용이 없는지 확인한다.
        # 구현 전에는 ModuleNotFoundError 로 RED 가 된다.
        import importlib
        # 부작용이 없으면 예외 없이 임포트가 완료되어야 한다.
        mod = importlib.import_module(
            "backtest.adapters.outbound.in_memory_backtest_engine"
        )
        assert mod is not None


class TestInMemoryBacktestEngine_run_스텁:
    def test_run_호출_시_NotImplementedError를_던진다(self):
        """WHY: M2 S3 스켈레톤은 인터페이스 계약만 존재하고 로직은 없다.
               NotImplementedError 는 "의도적 미구현" 을 명시하는 표준 방법이다."""
        from backtest.adapters.outbound.in_memory_backtest_engine import (
            InMemoryBacktestEngine,
        )
        engine = InMemoryBacktestEngine()
        with pytest.raises(NotImplementedError, match="M2 S4"):
            engine.run([], [])

    def test_run_빈_리스트_인자로_NotImplementedError_메시지에_M2_S4가_포함된다(self):
        """WHY: 오류 메시지에 다음 마일스톤 슬라이스 식별자가 있어야
               인계 문서 없이도 다음 담당자가 구현 위치를 파악할 수 있다."""
        from backtest.adapters.outbound.in_memory_backtest_engine import (
            InMemoryBacktestEngine,
        )
        with pytest.raises(NotImplementedError) as exc_info:
            InMemoryBacktestEngine().run(signals=[], price_history=[])
        assert "M2 S4" in str(exc_info.value)
