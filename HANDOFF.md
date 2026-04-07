# Sim_Money 핸드오프 문서

> 다른 PC / 다른 세션에서 이 프로젝트를 **끊김 없이 이어서 진행**하기 위한 안내서.
> 스키마 버전: v2
> 최종 업데이트: 2026-04-07

---

## 1. 프로젝트 개요

**Sim_Money** — 유사/반대 경향 종목을 찾는 웹앱으로 시작해 **1년 내 개인 전용 실거래·자동매매 시스템**으로 수렴하는 프로젝트.

- **엔드게임**: 본인 1인 전용 실거래 시스템 (Stage 3)
- **현재 단계**: Stage 1 / M1 — 유사도 탐색 MVP (3~4주)
- **대상**: 본인 전용. 제3자 공개 없음. Stage 3 진입 전 법률 검토 게이트 필수.
- **시장**: MVP 는 KOSPI200 + S&P500 (~700 종목)
- **스택**: Python 3.11+ / FastAPI / DuckDB / FinanceDataReader / Next.js 15+ TypeScript / shadcn/ui / KaTeX / Docker-compose
- **방법론**: Clean Architecture + Strategy 패턴 + DDD (L2) + L3 스켈레톤

상세 문서:
- 계획서: [`docs/plans/Sim_Money-plan.md`](docs/plans/Sim_Money-plan.md)
- ADR-000 엔드게임: [`docs/adr/ADR-000-endgame.md`](docs/adr/ADR-000-endgame.md)
- ADR-001 도메인 레벨: [`docs/adr/ADR-001-domain-levels.md`](docs/adr/ADR-001-domain-levels.md)
- ADR-002 Strategy 패턴: [`docs/adr/ADR-002-similarity-strategy-pattern.md`](docs/adr/ADR-002-similarity-strategy-pattern.md)

---

## 2. 다른 PC에서 이어 받기

### 2-1. 필수 도구

| 도구 | 버전 | 용도 |
|---|---|---|
| Git | 2.40+ | 소스 클론 |
| Docker Desktop | 최신 | docker-compose 실행 |
| Python | 3.11+ | 로컬 개발 (선택) |
| Node.js | 20+ | 로컬 프론트 개발 (선택) |

### 2-2. 클론 및 시크릿

```bash
git clone {repo-url}
cd Sim_Money
cp .env.example .env
# 시크릿 채우기 (현재 M1 에는 필수 시크릿 없음)
```

### 2-3. 실행

```bash
# M1 완료 후 (목표):
docker compose up

# 접속:
#   web : http://localhost:3000
#   api : http://localhost:8000/docs
```

### 2-4. 동작 확인 (smoke test)

```bash
# M1 완료 후 정의 예정
# 예: curl http://localhost:8000/similar/005930?n=5
```

---

## 3. 현재 진행 상태

### 현재 브랜치
`feature/market-data/pipeline-skeleton`

### 완료 ✅

| Phase | 항목 | 상태 | 브랜치 |
|---|---|---|---|
| Phase 0 | 프로젝트 뼈대 (HANDOFF v2, CI, 템플릿) | ✅ | main |
| Phase 0 | 계획서 + ADR-000/001/002 작성 | ✅ | main |
| M1 W1 S1 | L3 스켈레톤 + import-linter 계약 3건 + market_data 도메인 값 객체 (Ticker/AdjustedPrice/LogReturn) | ✅ | feature/market-data/pipeline-skeleton |
| M1 W1 S2 | PriceSeries 애그리거트 (불변식, log_returns, is_sufficient) | ✅ | feature/market-data/pipeline-skeleton |

### 🔴 블로커
없음

### 미완료 (다음 작업 순서) ⏳

1. **M1 W1 S3** — IngestPrices 유스케이스 + MarketDataSource/PriceRepository 포트 (헥사고날)
2. **M1 W1 S4** — FinanceDataReader 어댑터 + DuckDB 리포지토리 + 유니버스 도메인/스냅샷
2. **M1 W2** — Epic 2 (유사도 엔진 WeightedSum), 골든 회귀 테스트 GREEN
3. **M1 W3** — Epic 3 (FastAPI) + Epic 4 초안 (Next.js 기본 탐색)
4. **M1 W4** — Epic 4 완성 (슬라이더 + KaTeX) + Epic 5 (시각화) + Epic 6 (docker-compose)

### 알려진 미해결 이슈 / 주의사항

- [ ] 상관관계 ≠ 공적분. mean-reversion 보장 없음 — UI 고지 필수
- [ ] 체제변화(regime change) 취약성
- [ ] w1/w2/w3 가중치 경험적 (백테스트 전)
- [ ] shape/stability 중복 가능성 — Phase 2 재설계 후보
- [ ] Pearson 단독 (Spearman/공적분/DTW 는 Phase 2+)
- [ ] 생존편향 스냅샷 공시만, 완전 제거 아님
- [ ] 주가 데이터 라이선스 검토 (FDR/KRX 약관 문서화 필요)
- [ ] Stage 3 실거래 진입 전 법률 검토 게이트 (투자자문/일임/금투업 해당 여부)

---

## 4. 방법론 강제 규칙

### 도메인 엄격도 (ADR-001 참조)
- **L3** (`portfolio`, `signal`, `backtest`, `trading`, `risk`):
  - M1 은 **스켈레톤만**. 로직 0.
  - 로직 추가 순간 L3 엄격도 즉시 발동 — 90% 커버리지, ArchUnit, 단일 에이전트 금지.
- **L2** (`similarity`, `market_data`, `universe`):
  - DDD 애그리거트 + 80% 커버리지.
  - 포트/어댑터 분리, 값 객체 우선.
- **L1** (`ui_playground`, `visualization`, `notebooks`, `fixtures`, `docs`):
  - 프로토타입 허용.

### 경계 강제
- `import-linter` 로 L1/L2 → L3 금지, CI 검증.
- L3 → L2 는 허용.

### 전략 패턴 (ADR-002)
- 유사도 공식은 `SimilarityStrategy` 포트로만 호출.
- 하드코딩 금지.

---

## 5. 재개 체크리스트

새 세션에서 Claude 에게 다음을 먼저 실행하게 하라:

1. 이 문서(`HANDOFF.md`) 전체 읽기
2. `/bootstrap` 실행 (정합성 게이트)
3. `docs/plans/Sim_Money-plan.md`, `docs/adr/ADR-000~002` 확인
4. `git log --oneline --all --graph | head -30` 확인
5. 블로커가 있으면 먼저 해결
6. 없으면 "미완료" 섹션의 다음 우선순위 작업 시작

---

## 6. 참고 자료

- 계획서: `docs/plans/Sim_Money-plan.md`
- ADR: `docs/adr/`
- CI: `.github/workflows/ci.yml`
- 전역 지침: `~/.claude/CLAUDE.md`
- 프로젝트 지침: `CLAUDE.md`
