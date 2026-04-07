# ADR-001: 도메인 엄격도 L1/L2/L3 매핑 및 아키텍처 경계 강제

- 상태: Accepted
- 날짜: 2026-04-07
- 관련: [ADR-000](ADR-000-endgame.md)

## 컨텍스트

[ADR-000](ADR-000-endgame.md) 에서 엔드게임을 실거래 시스템으로 선언했다.
실거래 도메인은 전역 규칙상 L3 (Clean Arch + ArchUnit + 90% 커버리지 + 단일 에이전트 금지) 이다.
그러나 MVP(Stage 1) 는 플레이그라운드 UI 수준이라 L1 프로토타입이 적절하다.

**동일 저장소에서 L1 과 L3 가 공존해야 한다**. 이때 두 가지를 동시에 만족해야 한다:
1. MVP 개발 속도를 L3 오버헤드로 죽이지 않는다.
2. 나중에 거래 도메인을 붙일 때 L1 코드가 L3 경계를 침범하지 않는다.

## 결정

### 레벨 매핑

| 레벨 | 도메인 패키지 |
|---|---|
| **L3** | `portfolio/`, `signal/`, `backtest/`, `trading/`, `risk/` |
| **L2** | `similarity/`, `market_data/`, `universe/` |
| **L1** | `ui_playground/`, `visualization/`, `notebooks/`, `fixtures/`, `docs/` |

### 의존 방향 규칙

- L1 → L2 : 허용
- L3 → L2 : 허용 (L3 가 L2 를 재사용)
- **L1 → L3 : 금지**
- **L2 → L3 : 금지**
- L3 → L1 : 금지 (당연)

### 강제 수단

- `import-linter` 계약 파일을 리포에 커밋하고 CI 단계에 포함시킨다.
- 위반 시 CI 레드.

### M1 에서의 L3 취급

- L3 도메인은 **패키지 + 인터페이스 껍데기만** 생성한다. 로직 0.
- `KillSwitch`, `OrderGateway`, `PortfolioRepository` 등 포트 인터페이스만 선언.
- **레벨 승격 트리거**: L3 스켈레톤에 실제 로직이 한 줄이라도 추가되면 즉시 L3 엄격도 발동
  (테스트 커버리지 90%, ArchUnit 검증, 단일 에이전트 금지, `/develop` 또는 `/team-develop` 의무).

## 결과

### 긍정적
- MVP 는 L1/L2 속도로 진행된다.
- 거래 도메인 추가 시점에 L3 엄격도가 자동으로 발동된다.
- 경계 침범은 CI 가 자동 감시한다.

### 부정적
- M1 W1 에 L3 스켈레톤 + import-linter 설정 비용 발생.
- 개발자(본인)가 L3 트리거 규칙을 기억해야 한다 → CLAUDE.md 에 명시한다.

## 참고
- [전역 지침](~/.claude/CLAUDE.md) — 도메인 엄격도 정의
- [CLAUDE.md (프로젝트)](../../CLAUDE.md) — 레벨 매핑 반영
