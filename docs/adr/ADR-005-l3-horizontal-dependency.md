# ADR-005: L3 패키지 간 수평 의존 정책

- **상태**: Accepted
- **날짜**: 2026-04-08
- **연관**: ADR-001 (도메인 엄격도), ADR-003 (backtest L3), ADR-004 (portfolio L3), HANDOFF.md M3 S4

---

## 배경

M3 S4 에서 `backtest` 패키지가 `portfolio.adapters.outbound.EqualWeightStrategy` 를
어댑터 레이어에서 조립하면서 **첫 L3↔L3 수평 의존**이 발생했다.

L3 는 도메인 순수성과 프레임워크 격리를 엄격히 요구하는 레벨이다.
그러나 실거래 파이프라인(M3+)에서는 `trading → portfolio → risk` 같은
L3 간 협력이 불가피하다. 따라서 L3 수평 의존을 아예 금지하는 대신
**허용 레이어를 명확히 제한**하는 정책이 필요해졌다.

기존 ADR-001 은 L1→L3, L2→L3 수직 금지만 명시하며 L3↔L3 수평 의존에 대한
세부 정책이 부재했다.

---

## 결정 1: L3 수평 의존은 호출측 adapters 레이어에서만 허용

### 이유

- **도메인/애플리케이션 순수성 유지**: L3 도메인과 애플리케이션 레이어가 다른 L3 패키지에
  직접 의존하면 두 도메인의 경계가 유착된다. 포트 인터페이스로 분리된 의미가 사라진다.
- **어댑터가 조립 책임을 전담**: 헥사고날 아키텍처에서 어댑터는 외부 시스템과 도메인을
  연결하는 유일한 레이어다. 다른 L3 패키지도 어댑터 관점에서는 "외부 시스템"에 해당한다.
- **교체 용이성**: 호출측 어댑터만 수정하면 피호출 L3 패키지를 교체하거나 Mock 으로
  대체할 수 있어 테스트 격리가 유지된다.

### 허용/금지 규칙

| 레이어 | 다른 L3 import | 비고 |
|---|---|---|
| `<caller>.adapters.*` | **허용** | 조립 루트 역할 |
| `<caller>.application.*` | **금지** | 포트 인터페이스로 추상화 필수 |
| `<caller>.domain.*` | **금지** | 순수 도메인 유지 |

---

## 결정 2: 호출측 어댑터가 Anti-Corruption Layer 역할 전담

### 이유

- 피호출 L3 패키지의 도메인 타입이 호출측 도메인으로 직접 유입되면
  두 바운디드 컨텍스트의 언어가 혼재된다.
- 호출측 어댑터에서 외부 L3 타입 → 내부 DTO 변환을 수행해
  도메인 레이어는 자신의 VO/엔티티만 알도록 보호한다.

### 적용 예시

```
backtest.adapters.outbound.PortfolioPositionSizer
  ↓ portfolio.adapters.outbound.EqualWeightStrategy 호출
  ↓ portfolio.domain.TargetWeight → backtest 내부 Allocation DTO 변환
```

---

## 결정 3: import-linter 계약으로 CI 강제

각 L3 수평 의존 쌍에 대해 다음 형식의 계약을 `.importlinter` 에 추가한다.

```ini
[importlinter:contract:<caller>-no-<callee>-domain-application]
name = <caller>.domain/application must not import <callee>
type = forbidden
source_modules =
    <caller>.domain
    <caller>.application
forbidden_modules =
    <callee>
```

### M3 현재 적용 계약

- `backtest.domain/application must not import portfolio` — M3 S4 첫 적용

---

## 결과

- L3 패키지 간 수평 의존 정책 공식화. ADR-001 L3 엄격도 보완.
- M3 S4 의 `backtest → portfolio` 의존이 이 정책의 첫 적용 사례로 소급 적용된다.
- 이후 모든 L3 수평 의존(예: `trading → portfolio`, `trading → risk`)은
  이 정책에 따라 어댑터 레이어에서만 허용하며 별도 import-linter 계약을 추가한다.

### Stage 3 실거래 경로 영향

동일 정책 유지. `trading → portfolio`, `trading → risk`, `risk → portfolio` 등
실거래 L3 간 협력은 모두 호출측 `adapters` 레이어에서만 허용한다.
실거래 도메인 로직은 Stage 3 법률 검토 게이트 통과 이전까지 작성 금지이므로
이 정책은 게이트 이후 구현 시 기준이 된다.
