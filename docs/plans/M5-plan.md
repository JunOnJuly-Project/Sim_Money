# M5 — 리스크 관리 강화 (risk L3 활성화)

> 상태: 브레인스토밍 / 승인 대기
> 관련 ADR: [ADR-001](../adr/ADR-001-domain-levels.md) L3 엄격도, [ADR-005](../adr/ADR-005-l3-horizontal-dependency.md) L3↔L3 수평 의존 정책
> 선행 의존: M3 S15 PlanRebalance 제약 검증, M3 S13 그룹 사이징, backtest L3

## 1. 목적

Stage 3 (실거래) 진입 **이전에**, 백테스트 엔진과 리밸런싱 플래너가 공통으로 참조할 수 있는 **defensive 리스크 가드**를 `src/risk/` L3 도메인으로 정식 활성화한다. 목적은 "알려진 실패 모드를 코드로 차단"이다.

### 비목표 (Non-goals)
- 실시간 주문 라우팅·거래소 연동 (Stage 3 법률 게이트 이후)
- VaR/CVaR 같은 통계적 리스크 모델 (M6 후보)
- 동적 포지션 리밸런싱 알고리즘 (이미 portfolio 도메인 담당)

## 2. 핵심 가드 4종

| # | 가드 | 의미 | 체크 시점 |
|---|---|---|---|
| G1 | **PositionLimit** | 단일 심볼 최대 비중 / 최대 명목 금액 | 진입 전 |
| G2 | **StopLoss** | 포지션별 손실률이 한도 초과 시 강제 청산 | 매 bar |
| G3 | **MaxDrawdownCircuitBreaker** | 계좌 전체 누적 DD 한도 초과 시 신규 진입 차단 | 매 bar |
| G4 | **DailyLossLimit** | 당일 실현/미실현 손실 한도 초과 시 신규 진입 차단 | 매 bar (날짜 경계) |

네 가드는 **독립적 Protocol (포트)** 로 분리해 DIP·OCP 를 보장한다. 공용 인터페이스:

```python
class RiskGuard(Protocol):
    def check(self, ctx: RiskContext) -> RiskDecision: ...
```

`RiskDecision` = `Allow | BlockNew | ForceClose(symbol)`.

## 3. 브레인스토밍 (3 라운드 델파이 요약)

### 라운드 1 — 병렬 관점

- **planner**: 가드들을 한 번에 다 넣지 말고 G1 → G3 → G2 → G4 순서로 활성화. G1 은 이미 PortfolioConstraints 와 중복 소지 있으므로 **risk 쪽이 원본, portfolio 는 재노출**로 정리.
- **developer**: `RiskContext` 는 현재 equity / open positions / 당일 PnL / 누적 max equity 만 담는 불변 dataclass. 엔진이 매 bar 주입. 가드는 순수 함수(부작용 없음).
- **tester**: 각 가드는 **경계값 테스트 3종**(정확히 한도·한도 초과·한도 미만) + 골든 케이스로 "차단 없을 때 기존 수치 불변" 회귀.
- **reviewer**: `risk → backtest` import 금지. backtest 가 `risk` 를 의존해야 한다 (L3↔L3). ADR-005 에 risk 를 의존 허용 목록에 추가 필요.

### 라운드 2 — 교차 검토

- **planner → developer**: `RiskContext.positions` 를 직접 넘기면 backtest 도메인 타입(Position) 과 결합된다. risk 쪽에 독자 값 객체 `PositionSnapshot(symbol, qty, entry_price, current_price)` 를 정의하고 backtest 엔진이 매핑. 순환 의존 방지.
- **tester → planner**: G3 (DD 차단) 은 "한 번 트리거되면 어떻게 해제되는가" 정책이 필요. 단순화: **세션 내 해제 없음**(백테스트 구간 동안 유지). 실거래는 M6 에서 수동 리셋.
- **reviewer → all**: G2 강제 청산은 backtest `TradeExecutor` 에 close 경로가 이미 있어야 동작. 현재 있는지 확인 필요 → 있음(InMemoryTradeExecutor.close_position). OK.
- **developer → tester**: 각 가드 단위 테스트 + "가드 체인" 통합 테스트. 체인 순서: G1(진입차단) → G2(강제청산) → G3/G4(신규차단). 충돌 시 **가장 보수적 결정 우선**.

### 라운드 3 — 최종 통합

- risk 도메인 구조 확정:
  ```
  src/risk/
    domain/
      __init__.py
      limits.py              # PositionLimit, DrawdownLimit, DailyLossLimit, StopLossPolicy
      context.py             # RiskContext, PositionSnapshot
      decisions.py           # RiskDecision (Allow/BlockNew/ForceClose)
      errors.py
    application/
      ports/
        risk_guard.py        # RiskGuard Protocol
      use_cases/
        evaluate_risk.py     # 가드 체인 평가 유스케이스
    adapters/
      outbound/
        position_limit_guard.py
        stop_loss_guard.py
        drawdown_circuit_breaker.py
        daily_loss_limit_guard.py
  ```
- import-linter 계약 추가 (10 → 12 KEPT 목표):
  - `risk hexagonal layers`: domain → application → adapters
  - `risk domain purity` (no pandas/numpy)
- ADR 신규: `ADR-006-risk-l3-activation.md` (L3 활성화 선언 + 4 가드 사양)
- ADR-005 갱신: `backtest → risk`, `portfolio → risk` 수평 의존 명시 허용

## 4. Epic / Story / Task 분해

### Epic E1 — risk 도메인 활성화 (L3 엄격도 발동)

| Slice | 제목 | 산출 | 테스트 목표 |
|---|---|---|---|
| **M5 S1** | ADR-006 + 도메인 값 객체 (RiskContext, PositionSnapshot, RiskDecision) + errors | ADR, `domain/context.py`, `domain/decisions.py` | 값 객체 불변식 |
| **M5 S2** | `RiskGuard` 포트 + `EvaluateRisk` 유스케이스 (체인 평가, 보수적 우선 규칙) | `application/ports/`, `application/use_cases/evaluate_risk.py` | 체인 순서·충돌 케이스 |
| **M5 S3** | `PositionLimitGuard` (G1) 어댑터 + 경계값 3종 테스트 | adapter + tests | 커버리지 100% |
| **M5 S4** | `DrawdownCircuitBreaker` (G3) 어댑터 + 세션 상태 추적 | adapter + tests | 트리거 후 신규 진입 차단 확인 |
| **M5 S5** | `StopLossGuard` (G2) 어댑터 + ForceClose 결정 | adapter + tests | 강제 청산 결정 생성 |
| **M5 S6** | `DailyLossLimitGuard` (G4) 어댑터 + 날짜 경계 리셋 | adapter + tests | 자정 경계 리셋 회귀 |
| **M5 S7** | import-linter `risk` 계약 2건 추가 (10 → 12 KEPT) + ADR-005 갱신 | `.importlinter`, ADR | CI GREEN |

### Epic E2 — backtest 통합

| Slice | 제목 | 산출 |
|---|---|---|
| **M5 S8** | `RunBacktest` 에 `risk_guards: Sequence[RiskGuard] \| None = None` 주입. 매 bar `EvaluateRisk.evaluate(context, guards)` 호출. 결정에 따라 진입 skip / close. 기본 None 이면 기존 거동 불변 |
| **M5 S9** | `BacktestConfig` 에 `risk_limits: RiskLimits \| None` 추가 + 팩토리로 기본 가드 체인 조립 |
| **M5 S10** | 골든 케이스 회귀 — 가드 비활성 시 수치 불변 확인 (기존 테스트 전부 GREEN 유지) + 가드 활성 골든 2종 신규 |

### Epic E3 — portfolio / API / UI

| Slice | 제목 | 산출 |
|---|---|---|
| **M5 S11** | `PlanRebalance` 가 `PositionLimitGuard` 를 **재사용**해 기존 `max_position_weight` 검증을 risk 도메인으로 위임 (DRY). 기존 테스트 전부 GREEN 유지 |
| **M5 S12** | `/backtest/pair` `risk_*` 쿼리 파라미터 (position_limit, stop_loss_pct, max_dd, daily_loss) + config 에코 |
| **M5 S13** | 백테스트 대시보드 UI — 리스크 입력 섹션 (접이식) + 결과에 "리스크 트리거 이벤트 타임라인" 카드 |

## 5. 작업 순서 (제안)

TDD 커밋 순서 (ADR-001 L3 규칙):
1. S1 (ADR + 값 객체)
2. S2 (포트 + 유스케이스) — 먼저 실패 테스트, 다음 구현
3. S3 → S4 → S5 → S6 (가드 어댑터, 각 슬라이스마다 RED→GREEN→REFACTOR)
4. S7 (계약)
5. S8 → S9 → S10 (백테스트 통합)
6. S11 (portfolio 재사용)
7. S12 → S13 (API/UI)

각 슬라이스는 독립 빌드 통과·main 머지 가능.

## 6. 리스크 목록

| # | 리스크 | 완화 |
|---|---|---|
| R1 | 기존 골든 케이스 수치 깨짐 (가드 기본 None 이어도 코드 경로 변경으로) | S10 에서 회귀 테스트 **먼저** 작성. 기본 None 경로 no-op 보장 |
| R2 | `backtest → risk` 의존 추가로 import-linter 레드 | S7 에서 ADR-005 갱신과 동시 머지 |
| R3 | G3/G4 세션 상태가 stateful → 순수 함수 가정 깨짐 | 세션 상태를 `RiskContext` 에 외부 주입, 가드는 여전히 순수 |
| R4 | PlanRebalance 의 기존 제약과 PositionLimit 이중화 | S11 에서 명시적 위임. PortfolioConstraints 는 얇은 래퍼로 유지 |
| R5 | L3 엄격도 위반 (단일 에이전트 작성) | 각 슬라이스 `/develop` 또는 `/team-develop` 팀 파이프라인 사용 강제 |
| R6 | UI 복잡도 폭증 | S13 는 접이식 섹션 + 기본값으로 기존 사용자 워크플로 보호 |

## 7. 수용 기준 (Definition of Done)

- [ ] 테스트 수 599+ GREEN (현재 499 + 약 100)
- [ ] import-linter 12 KEPT
- [ ] risk 도메인 커버리지 ≥ 95%
- [ ] backtest 커버리지 회귀 없음 (≥ 97%)
- [ ] 모든 기존 골든 케이스 수치 불변
- [ ] ADR-006 머지, ADR-005 갱신
- [ ] HANDOFF.md M5 슬라이스 행 전부 ✅
- [ ] README 리스크 가드 설명 섹션 추가

## 8. 승인 대기 항목

- [ ] Epic 분해 및 슬라이스 순서
- [ ] 4 가드 스펙 (한도·트리거 정책)
- [ ] `RiskGuard` Protocol 시그니처 초안
- [ ] import-linter 계약 추가 범위

사용자 승인 후 `M5 S1` 부터 `/develop` 팀 파이프라인으로 착수.
