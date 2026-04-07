# ADR-004: portfolio 패키지 L3 엄격도 활성화 및 WeightingStrategy 포트 도입

- **상태**: Accepted
- **날짜**: 2026-04-07
- **연관**: ADR-000, ADR-001, ADR-002, ADR-003, HANDOFF.md M2 feature/portfolio/position-sizing

---

## 배경

M1 에서 `portfolio` 패키지는 L3 스켈레톤(패키지 + `__init__.py` 로직 0줄)으로
유지됐다. M2/M3 로드맵 상 position-sizing 슬라이스가 시작되며
**CLAUDE.md L3 엄격도 발동 조건**이 충족됐다.

ADR-003(backtest L3 활성화) 패턴을 그대로 미러링한다.

발동 시점 목표 지표:
- 테스트 커버리지 90%+ (L3 요건)
- import-linter 계약: portfolio hexagonal layers + domain/application purity (no pandas/numpy)
- 단일 에이전트 금지 규칙 준수 (다중 에이전트 파이프라인으로 구현)

---

## 결정 1: portfolio 도메인 스코프 — 사이징·리밸런싱만

### 이유

- portfolio 는 "어떤 비중으로 보유할 것인가"와 "현재 → 목표 사이 주문 의도"만 책임진다.
- 실거래 주문 실행(trading 도메인)·리스크 한도 관리(risk 도메인)는 별도 L3 도메인이 담당한다.
- M1 스켈레톤 단계부터 확정된 경계로, Stage 3(실거래) 경로를 막지 않는다.

### 스코프 경계

| 포함 | 제외 |
|---|---|
| `TargetWeight` (목표 비중 VO) | 실거래 주문 실행 |
| `CurrentPosition` (현재 포지션 VO) | 리스크 한도 검증 |
| `PortfolioConstraints` (제약 VO) | 세금·수수료 계산 |
| `RebalancePlan` / `OrderIntent` | 시장가·지정가 전략 |
| `WeightingStrategy` 포트 | 백테스트 성과 계산 |
| `ComputeTargetWeights` 유스케이스 | |
| `PlanRebalance` 유스케이스 | |
| `EqualWeightStrategy` 어댑터 | |

---

## 결정 2: WeightingStrategy 포트 — Strategy 패턴 (ADR-002 미러링)

### 이유

- 동일 interface 뒤에 EqualWeight / RiskParity / MeanVariance 등 전략을 교체 가능하게 한다.
- ADR-002(SimilarityStrategy)와 동일한 패턴을 적용해 학습 부담을 줄인다.
- M3 에서 backtest outbound 어댑터가 WeightingStrategy 를 소비할 때 인터페이스 변경 없이 전략만 교체한다.

### 포트 시그니처

```python
class WeightingStrategy(Protocol):
    def compute(
        self,
        signals: Sequence[SignalInput],
        constraints: PortfolioConstraints,
    ) -> tuple[TargetWeight, ...]: ...
```

### SignalInput DTO

외부 `trading_signal` 패키지에 대한 의존을 끊기 위해 portfolio 자체 DTO 정의.

```python
@dataclass(frozen=True)
class SignalInput:
    symbol: str
    score: Decimal
```

---

## 결정 3: Decimal 가중치 + 합계 epsilon=1e-9

### 이유

- 가중치 합 검증에서 float 오차로 인한 오탐을 방지한다.
- `Decimal("1") - sum(weights)` 가 `Decimal("1e-9")` 이하이면 정규화 완료로 간주한다.
- ADR-003(Signal.strength Decimal 전환)과 일관성을 유지한다.

---

## 결정 4: M3 한정 EqualWeightStrategy 1개 구현

### 이유

- M2/M3 MVP 에서는 균등 분배로 파이프라인 검증이 충분하다.
- 추가 전략(RiskParity, MeanVariance, Spearman 상관 기반)은 동일 포트 구현으로 확장한다.
- Phase 2+ 전략 추가 시 ADR-002 패턴에 따라 별도 ADR 을 작성한다.

### 캡 로직

- `max_position_weight` 초과 시 초과분을 나머지 종목에 균등 재분배 (1회).
- `cash_buffer` 반영: 합 = 1 - buffer.

---

## 결정 5: 다음 슬라이스 — backtest outbound 통합

M3 에서 `backtest.application.ports` 에 `WeightingStrategyPort` 어댑터를 추가해
`portfolio.adapters.outbound` 의 `EqualWeightStrategy` 를 백테스트 파이프라인에 연결한다.
이 연결은 별도 ADR 로 기록한다.

---

## 결과

- `portfolio` 패키지 L3 엄격도 공식 활성화.
- import-linter: `portfolio hexagonal layers` + `portfolio domain/application purity` 계약 추가.
- 이후 `portfolio` 패키지 변경은 L3 엄격도 전적 적용:
  - 커버리지 90%+ 유지 의무
  - 단일 에이전트 구현 금지
  - `pandas`, `numpy` 를 도메인/애플리케이션 레이어에서 직접 import 금지
