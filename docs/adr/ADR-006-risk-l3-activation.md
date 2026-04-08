# ADR-006: risk 도메인 L3 활성화

- 상태: Accepted
- 날짜: 2026-04-08
- 관련: [ADR-001](ADR-001-domain-levels.md) 도메인 엄격도, [ADR-005](ADR-005-l3-horizontal-dependency.md) L3↔L3 수평 의존 정책

## 컨텍스트

`src/risk/` 는 M1 이후 스켈레톤 상태였다. Stage 3 (실거래) 진입 이전에 **alan failure mode 를 코드로 차단**하는 defensive 가드 계층이 필요하다. 기존 `portfolio.PortfolioConstraints` 는 리밸런싱 시점의 정적 제약만 담당하며, 실시간 손실/드로다운/스탑로스 같은 동적 가드는 없다.

## 결정

`risk` 를 L3 도메인으로 정식 활성화한다. 헥사고날 아키텍처 + DDD 값 객체 + TDD 엄격도를 적용한다.

### 4 가드

| 코드 | 이름 | 트리거 |
|---|---|---|
| G1 | PositionLimit | 단일 심볼 비중/명목 초과 시 진입 차단 |
| G2 | StopLoss | 포지션 손실률이 한도 초과 시 강제 청산 |
| G3 | MaxDrawdownCircuitBreaker | 계좌 누적 DD 한도 초과 시 신규 진입 차단 |
| G4 | DailyLossLimit | 당일 손실 한도 초과 시 신규 진입 차단 |

### 공통 Protocol

```python
class RiskGuard(Protocol):
    def check(self, ctx: RiskContext) -> RiskDecision: ...
```

`RiskDecision` 은 합집합: `Allow | BlockNew | ForceClose(symbol)`. 체인 평가 시 **가장 보수적 결정이 우선**한다 (ForceClose > BlockNew > Allow).

### L3↔L3 수평 의존

ADR-005 를 갱신해 다음을 허용한다:
- `backtest → risk` (엔진이 가드 체인 호출)
- `portfolio → risk` (PlanRebalance 가 PositionLimit 재사용)

`risk → backtest` / `risk → portfolio` 는 **금지**. risk 는 타 L3 도메인을 모르는 "리프 도메인" 이다.

### 값 객체 순수성

`risk.domain` 은 pandas/numpy 금지. `Decimal` + stdlib 만 사용한다. import-linter 계약 2건을 S7 에서 추가한다 (hexagonal layers + domain purity).

## 결과

- **긍정**: Stage 3 전에 방어 로직이 도메인으로 명문화됨. backtest 에 가드 주입으로 과거 실패 모드 회귀 방지.
- **부정**: L3↔L3 의존이 늘어 아키텍처 복잡도 증가. 각 가드 어댑터마다 경계값 테스트 필요.
- **대안 기각**: "portfolio 도메인 내부에 리스크 로직 추가" 는 SRP 위반. "risk 를 L2 로" 는 실거래 직결 도메인이라 엄격도 낮출 수 없음.

## 참고

- 슬라이스 분해: [`docs/plans/M5-plan.md`](../plans/M5-plan.md)
