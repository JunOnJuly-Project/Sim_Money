# Sim_Money 프로젝트 로컬 지침

> 이 파일은 전역 `~/.claude/CLAUDE.md` 를 **덮어쓰지 않고 보완**한다.
> 관련 ADR: [ADR-000](docs/adr/ADR-000-endgame.md), [ADR-001](docs/adr/ADR-001-domain-levels.md), [ADR-002](docs/adr/ADR-002-similarity-strategy-pattern.md)

## 프로젝트 엔드게임

**1년 내 개인 전용 실거래·자동매매 시스템**으로 수렴한다. 현재는 Stage 1 (MVP, 유사도 탐색).
모든 M1 코드는 Stage 3(실거래) 경로를 막아서는 안 된다.

## 도메인 엄격도 (L1-L3)

| 레벨 | 특성 | 적용 대상 예시 |
|---|---|---|
| **L3** (최엄격) | Clean Arch + ArchUnit + 90% 커버리지 + 단일 에이전트 금지 | 결제/주문/보안/실거래 핵심 |
| **L2** | DDD 애그리거트 + 80% 커버리지 | 회원/상품/도메인 서비스 |
| **L1** | 프로토타입 허용 | 프런트엔드/문서/파사드 |

### 이 프로젝트의 레벨 매핑

- **L3**: `portfolio/`, `signal/`, `backtest/`, `trading/`, `risk/`
  - M1 에서는 **스켈레톤만** (패키지 + 포트 인터페이스, 로직 0)
  - 로직 추가 순간 L3 엄격도 즉시 발동
- **L2**: `similarity/`, `market_data/`, `universe/`
- **L1**: `ui_playground/`, `visualization/`, `notebooks/`, `fixtures/`, `docs/`

### 의존 방향 규칙 (import-linter 로 CI 강제)

- L1 → L2 : 허용
- L3 → L2 : 허용
- **L1 → L3 : 금지**
- **L2 → L3 : 금지**

## 브랜치 전략

`github-flow` — `main` + `feature/{도메인}/{기능-kebab}` 단기 브랜치.

## 커밋 순서 규칙 (L3 전용)

1. 포트 정의
2. 실패 테스트
3. 유스케이스 구현
4. 어댑터 구현
5. ArchUnit + 통합 테스트
6. (선택) 리팩터

각 커밋은 **독립적으로 빌드 통과**해야 한다.

## 유사도 공식 규칙 (ADR-002)

- 공식은 `SimilarityStrategy` 포트로만 호출한다. 직접 하드코딩 금지.
- M1 에는 `WeightedSumStrategy` 1개만 구현.
- Phase 2+ 전략(Spearman, 공적분, DTW, DCC-GARCH)은 같은 인터페이스의 추가 구현으로 도입.

## 금지 사항

- **L1 또는 L2 코드에서 L3 모듈 import 금지** (CI 검증).
- **L3 스켈레톤에 로직 추가 시 즉시 L3 엄격도 발동** — 커버리지 90%, ArchUnit, 단일 에이전트 금지,
  반드시 `/team-develop` 또는 `/develop` 다중 에이전트 파이프라인 사용.
- 단일 에이전트로 L3 기능 작성 후 커밋 금지.
- L3 도메인에서 `org.springframework.*`, `jakarta.persistence.*` 등 프레임워크 직접 import 금지
  (Python 환경에서는 FastAPI, SQLAlchemy, pandas 등 인프라 라이브러리의 L3 직접 import 금지).
- **실거래 관련 실제 로직 작성 금지** — Stage 3 법률 검토 게이트 통과 이전까지.
- UI 에서 개인 사용 고지 문구 제거 금지.
