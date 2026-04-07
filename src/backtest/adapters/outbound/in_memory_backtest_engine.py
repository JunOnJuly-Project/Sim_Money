"""
인메모리 백테스트 엔진 어댑터 스켈레톤.

WHY: M2 S3 단계에서는 포트 계약 존재와 NotImplementedError 계약만 확립한다.
     실제 엔진 로직을 추가하는 순간 L3 엄격도(커버리지 90%, 다중 에이전트)가
     즉시 발동되므로 구현은 M2 S4 이후 `/develop` 파이프라인을 통해 진행해야 한다.
"""
from __future__ import annotations


class InMemoryBacktestEngine:
    """M2 S3 스켈레톤. 로직 추가 시 L3 엄격도 발동."""

    def run(self, signals, price_history):
        """백테스트를 실행한다.

        WHY: M2 S4 에서 구현 예정. 지금은 NotImplementedError 로
             의도적 미구현 상태임을 명시해 다음 담당자가 즉시 파악할 수 있게 한다.
        """
        raise NotImplementedError(
            "M2 S4 스켈레톤. M2 S4 이후 L3 엄격도(커버리지 90%, 다중 에이전트) 하에 구현."
        )
