# ADR-007: ExitAdvisor 포트와 강제 청산 경로

상태: Accepted (2026-04-08)
관련: ADR-005 (L3↔L3 수평 의존), ADR-006 (risk L3 활성화)

## 배경

M5 S8/S9 에서 도입한 `EntryFilter` 는 진입 후보를 차단하는 데만 사용된다.
`StopLossGuard` 가 반환하는 `ForceClose` 결정은 보유 포지션의 즉시 청산을
요구하지만, EntryFilter 의 책임 범위를 벗어나므로 별도 경로가 필요하다.

## 결정

`backtest.application.ports.exit_advisor.ExitAdvisor` 포트를 신설한다.

```python
class ExitAdvisor(Protocol):
    def advise(
        self,
        timestamp: datetime,
        positions: Mapping[str, PositionView],
        available_cash: Decimal,
        equity: Decimal,
    ) -> Sequence[str]: ...
```

- `PositionView` 는 application 레이어 내부 dataclass (Decimal/stdlib only).
  risk 도메인 타입을 application 으로 누출하지 않는다.
- `RunBacktest` 는 advisor 가 주입되면 매 bar (신호 timestamp ∪ bar timestamp)
  에서 호출하고, 반환된 심볼을 합성 EXIT 신호로 변환해 기존 EXIT 처리 파이프에 합류시킨다.
- advisor=None 이면 기존 동작(신호 timestamp 만 순회) 그대로 유지 → 골든 회귀 0.

어댑터 `RiskExitAdvisor` 는 `backtest.adapters.outbound` 에서 `StopLossGuard`
체인을 래핑한다 (ADR-005: L3↔L3 수평 의존은 어댑터 레이어에서만).

## 결과

- ✅ 진입 차단(EntryFilter) ↔ 강제 청산(ExitAdvisor) 책임 분리
- ✅ application 레이어 risk 의존 없음 — import-linter 12 KEPT 유지
- ✅ advisor=None 기본값으로 골든 케이스 570 GREEN 보존
- ⚠️ advisor 활성 시 equity_curve 가 더 조밀해진다 (bar 단위 스냅샷 추가).
  Sharpe/Sortino 비율 분포가 달라질 수 있으므로 가드 ON/OFF 결과를 직접 비교할 때 주의.

## 대안

- EntryFilter 를 확장해 청산까지 처리 — 책임 비대화·인터페이스 오염으로 기각
- 엔진 내부에 가드 직접 호출 — application → risk 직접 의존 발생 (ADR-005 위반)
