# ADR-003: backtest 패키지 L3 엄격도 활성화 및 Signal.strength Decimal 정규화

- **상태**: Accepted
- **날짜**: 2026-04-07
- **연관**: ADR-000, ADR-001, ADR-002, HANDOFF.md M2 S4

---

## 배경

M2 S3 에서 `backtest` 패키지는 L3 스켈레톤(포트 인터페이스 + 로직 0줄)으로 시작했다.
M2 S4 에서 BacktestConfig, RunBacktest 이벤트 루프, InMemoryTradeExecutor,
RatioPerformanceCalculator, InMemoryBacktestEngine 이 실구현으로 전환되며
**CLAUDE.md L3 엄격도 발동 조건**이 충족됐다.

발동 시점 달성 지표:
- 테스트 커버리지 97% (L3 요건 90% 초과)
- import-linter 계약 5 KEPT (헥사고날 layers + domain/application purity)
- 단일 에이전트 금지 규칙 준수 (다중 에이전트 파이프라인으로 구현)

M2 S4 리뷰(R1) 완료 후, 이월된 [중요] 항목으로 두 가지 결정이 필요해졌다:

1. `Signal.strength` 타입이 `float` 로 남아 있어 `Decimal` 수량 계산 경계에서
   `Decimal(str(strength))` 변환이 노출됨 → 타입 경계 불일치.
2. `_calc_sharpe` M2 한정 단순화 사실이 코드 내 docstring 에만 있고
   ADR 에 공식 기록되지 않음 → 의도 추적 불가.

---

## 결정 1: Signal.strength 타입을 float → Decimal 로 전환

### 이유

- `InMemoryTradeExecutor._calc_quantity` 내부에서 `Decimal(str(strength))` 변환이
  불필요하게 노출돼 타입 계약이 모호해진다.
- float 정밀도 오차가 Decimal 수량 계산에 누적될 가능성이 있다.
- 골든 케이스 테스트에서 `Decimal("0.5")` 같은 정확한 assert 가 어렵다.
- `Signal` 은 L3 도메인 값 객체이므로 Decimal 일관성이 필수다.

### 변경 범위

- `src/backtest/domain/signal.py`: `strength: float` → `strength: Decimal`
- `src/backtest/adapters/outbound/in_memory_trade_executor.py`:
  `_calc_quantity` 시그니처 `strength: Decimal`, `Decimal(str(...))` 변환 제거
- 모든 테스트 파일: `strength=0.5` → `strength=Decimal("0.5")` 일괄 수정

### 결과

- 타입 경계가 명확해져 `float → Decimal` 변환 지점이 사라진다.
- 골든 케이스 assert 가 `Decimal` 리터럴로 정밀 비교 가능해진다.

---

## 결정 2: _calc_sharpe M2 한정 단순화 유지 (무위험=0, 등간격 가정)

### 이유

- M2 목적은 백테스트 파이프라인 검증이며, 정밀한 샤프 계산은 M3 스코프다.
- 무위험 수익률 데이터 소스(국채 수익률 API 등)는 M3 인프라 결정이 필요하다.
- 현재 equity_curve 가 등간격 bar 를 가정하므로, 실제 거래일 간격 보정은
  M3 에서 별도 ADR 로 다뤄야 한다.

### 단순화 내용

- 무위험 수익률 = 0 (차감 없음)
- equity_curve 등간격 가정 (실제 거래일 간격 미적용)
- 연율화 인수: sqrt(252) 고정

### 정식 구현 시점

M3 에서 별도 ADR 로 정식 샤프 구현(실제 trading day 간격, 무위험 수익률 차감) 진행.

---

## 결정 3: equity_curve 매 bar 종료 시 mark-to-market 기록

M2 S4 R1 에서 이미 반영됨. 기록 목적으로 명시.

- 매 bar 종료 시 current close 기준 mark-to-market 으로 equity_curve 를 기록한다.
- WHY: 포지션 보유 중 자본 평가는 현재 시장가 기준이어야 실제 포트폴리오 가치를
       정확히 반영한다.

---

## 결과

- `Signal.strength` 가 `Decimal` 로 통일돼 L3 타입 일관성 확보.
- `_calc_sharpe` 단순화가 ADR 수준에서 공식 기록되어 M3 정식 구현 시 추적 가능.
- backtest L3 진입이 공식화됨: 이후 backtest 패키지 변경은 L3 엄격도 전적으로 적용.
- import-linter 5 KEPT, 커버리지 90%+ 유지 의무.
