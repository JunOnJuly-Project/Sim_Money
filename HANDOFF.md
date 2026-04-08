# Sim_Money 핸드오프 문서

> 다른 PC / 다른 세션에서 이 프로젝트를 **끊김 없이 이어서 진행**하기 위한 안내서.
> 스키마 버전: v2
> 최종 업데이트: 2026-04-08

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
`main` (M2 MVP 완료)

### 완료 ✅

| Phase | 항목 | 상태 | 브랜치 |
|---|---|---|---|
| Phase 0 | 프로젝트 뼈대 (HANDOFF v2, CI, 템플릿) | ✅ | main |
| Phase 0 | 계획서 + ADR-000/001/002 작성 | ✅ | main |
| M1 W1 S1 | L3 스켈레톤 + import-linter 계약 3건 + market_data 도메인 값 객체 (Ticker/AdjustedPrice/LogReturn) | ✅ | feature/market-data/pipeline-skeleton |
| M1 W1 S2 | PriceSeries 애그리거트 (불변식, log_returns, is_sufficient) | ✅ | feature/market-data/pipeline-skeleton |
| M1 W1 S3 | IngestPrices 유스케이스 + MarketDataSource/PriceRepository 포트 (헥사고날) | ✅ | feature/market-data/pipeline-skeleton |
| M1 W1 S4 | FinanceDataReaderSource 어댑터 (lazy import, FakeReader 격리) | ✅ | feature/market-data/pipeline-skeleton |
| M1 W1 S5 | DuckDBPriceRepository 어댑터 (멱등 INSERT OR REPLACE, in-memory 테스트) | ✅ | feature/market-data/pipeline-skeleton |
| M1 W1 S6 | UniverseSnapshot 애그리거트 + UniverseSource 포트 (생존편향 명시) | ✅ | feature/market-data/pipeline-skeleton |
| M1 W1 | → main 머지 (`d9b5942`) | ✅ | main |
| M1 W2 S1 | Correlation 값 객체 + pearson_correlation + SimilarityStrategy 포트 | ✅ | feature/similarity/weighted-sum-strategy |
| M1 W2 S2 | WeightedSumStrategy + SimilarityWeights (ADR-002 M1 단순화) | ✅ | feature/similarity/weighted-sum-strategy |
| M1 W2 S3 | 골든 회귀 테스트 T-REG-01~05 (결정론적 픽스처) | ✅ | feature/similarity/weighted-sum-strategy |
| M1 W2 | → main 머지 (`10538ca`) | ✅ | main |
| M1 W3 S1 | FindSimilarTickers 유스케이스 + PriceRepository.load 포트 확장 | ✅ | feature/api/find-similar |
| M1 W3 S2 | DuckDBPriceRepository.load 구현 (멱등 재조회) | ✅ | feature/api/find-similar |
| M1 W3 S3 | FastAPI 인바운드 어댑터 (/health, /similar/{symbol}) | ✅ | feature/api/find-similar |
| M1 W3 | 백엔드 → main 머지 (`f83b131`) | ✅ | main |
| M1 W3 S4 | Next.js 15 탐색 UI 스캐폴드 (/, 폼+결과 테이블, 고지 배너) | ✅ | feature/web/explore-ui |
| M1 W4 S1 | FastAPI w1/w2/w3 쿼리 + 프론트 슬라이더/KaTeX 플레이그라운드 | ✅ | feature/web/formula-playground |
| M1 W4 S2 | GET /pair 엔드포인트 + 프론트 산점도/롤링 상관 차트 (recharts) | ✅ | feature/web/formula-playground |
| M1 W4 S3 | docker-compose (api+web) + ASGI 부트스트랩 + smoke 테스트 | ✅ | feature/web/formula-playground |
| M1 MVP | M1 전체 완료 (161 테스트 GREEN, import-linter 3 KEPT, L3 로직 0줄) | ✅ | main `0ce031c` |
| M2 S1 | SpearmanStrategy (main `bbeff9c`) | ✅ | main |
| M2 S2 | CointegrationStrategy Engle-Granger (main `043d609`) | ✅ | main |
| M2 S3 | backtest L3 스켈레톤 — 도메인 값 객체/포트 Protocol/어댑터 스텁 (246 GREEN) | ✅ | main |
| M2 S4 | backtest L3 실구현 — BacktestConfig/RunBacktest 이벤트 루프/TradeExecutor/PerformanceCalculator/Engine 조립 (294 GREEN, backtest 커버리지 97%, import-linter 5 KEPT) | ✅ | feature/backtest/engine-impl |
| M2 S4 리뷰 R1 | 중복 LONG 드랍(seen 세트), equity_curve mark-to-market (current close), 타입 힌트 정밀화, _calc_sharpe M2 한정 단순화 docstring (96 GREEN, 97%, 5 KEPT) | ✅ | main |
| M2 S4.5 | ADR-003 + Signal.strength float→Decimal 마이그레이션 + Sharpe docstring 보강 (295 GREEN, 97%, 5 KEPT) | ✅ | main |
| M2 S5 | trading_signal L3 패키지 활성화 — Pair/ZScore/TradingSignal 도메인 + GeneratePairSignals 유스케이스 + PairTradingSignalSource 어댑터. stdlib `signal` 충돌 회피 위해 `trading_signal` 로 리네임. 335 GREEN, 커버리지 99%, 7 KEPT (trading_signal layers + purity 추가) | ✅ | feature/signal/pair-trading-source |
| M2 S6 | 백테스트 웹 대시보드 — GET /backtest/pair/{a}/{b} 엔드포인트 + TradingSignal→backtest.Signal 변환 + Next.js /backtest 라우트 (Metrics/Equity/Trades 차트). similarity.adapters.inbound 조립 루트 예외 (import-linter ignore_imports + 아키텍처 테스트 composition root marker). 342 GREEN, 7 KEPT | ✅ | feature/web/backtest-dashboard |
| M2 MVP | M2 전체 완료 (342 테스트 GREEN, 7 import-linter KEPT, backtest 97% / trading_signal 99% 커버리지) | ✅ | main |
| infra | docker compose 부트스트랩 픽스 (Dockerfile.api 순서, next.config 프록시 분리, 시드 10종 확장) | ✅ | main `b045b6d` |
| M3 S1 | RatioPerformanceCalculator Sharpe 정식 구현 — risk_free_rate, 등간격 검증, ddof=1 표본 표준편차, equity≤0 가드, timestamp 타입 가드 (363 GREEN, 7 KEPT) | ✅ | feature/backtest/sharpe-formal |
| M3 S2 | risk_free_rate 끝단 노출 — BacktestConfig 필드/불변식, RunBacktest→PerformanceCalculator 전달, /backtest/pair rfr 쿼리, 대시보드 입력 필드 (372 GREEN, 7 KEPT) | ✅ | feature/backtest/risk-free-rate-config |
| M3 S3 | portfolio L3 활성화 — ADR-004 + 도메인(TargetWeight/Constraints/RebalancePlan) + WeightingStrategy 포트 + ComputeTargetWeights/PlanRebalance 유스케이스 + EqualWeightStrategy 어댑터. 423 GREEN, 9 KEPT, 커버리지 92% | ✅ | feature/portfolio/position-sizing |
| M3 S4 | backtest ↔ portfolio 통합 — PositionSizer 포트 + StrengthPositionSizer(기본) + PortfolioPositionSizer(WeightingStrategy 래퍼) + InMemoryTradeExecutor 리팩터 + L3↔L3 의존 계약 명문화. 436 GREEN, 10 KEPT | ✅ | feature/backtest/portfolio-integration |
| M3 S5 | sizer 선택 API/UI — /backtest/pair `sizer=strength\|equal_weight` 쿼리 + 대시보드 토글 + _calc_quantity 매개변수명 리팩터 + 비제로 비용 회귀 테스트. 438 GREEN, 10 KEPT | ✅ | feature/api/sizer-selection |
| M3 S6 | ADR-005 L3 수평 의존 정책 + /backtest/pair max_position_weight/cash_buffer 쿼리 + UI 조건부 제약 입력 블록. 441 GREEN, 10 KEPT | ✅ | feature/api/portfolio-constraints |
| M3 S7 | POST /portfolio/rebalance — PlanRebalance 유스케이스 HTTP 노출 + 7 테스트 GREEN, 10 KEPT | ✅ | feature/api/portfolio-rebalance |
| M3 S8 | portfolio 커버리지 100% — EqualWeightStrategy 사도(死道) 분기 제거 + errors.py 테스트 + plan_rebalance total_equity=0 분기 테스트. 453 GREEN, 10 KEPT | ✅ | chore/portfolio/coverage |
| M3 S9 | 리밸런싱 플래너 UI (/rebalance) — 현재 포지션/목표 가중치 동적 폼 + 합계 검증 + BUY/SELL 결과 테이블 + 홈 네비 링크 | ✅ | feature/web/rebalance-planner |
| M3 S10 | ScoreWeightedStrategy — 두 번째 WeightingStrategy (score 비율 가중, 합=0 폴백, 캡 적용) + /backtest/pair sizer=score_weighted 옵션 + UI 토글. 463 GREEN, 10 KEPT | ✅ | feature/portfolio/score-weighted |
| M3 S11 | POST /portfolio/compute — ComputeTargetWeights HTTP 노출 (equal/score 전략 선택, cash_buffer/max_position_weight 적용). 470 GREEN, 10 KEPT | ✅ | feature/api/portfolio-compute |
| M3 S12 | /backtest/pair 응답에 config 에코 추가 + 대시보드 설정 카드 표시. 471 GREEN, 10 KEPT | ✅ | feature/api/backtest-metadata |
| M3 S13 | 백테스트 엔진 그룹 단위 포트폴리오 사이징 (PositionSizer.size_group, initial_cash 스냅샷). 477 GREEN, 10 KEPT | ✅ | feature/backtest/group-sizing |
| M3 S14 | Sortino·Calmar 리스크 지표 추가 + API 응답 노출. 482 GREEN, 10 KEPT | ✅ | feature/backtest/sortino-calmar |
| M3 S15 | PlanRebalance 제약 사후 검증 (max_position_weight / cash_buffer → ConstraintViolation). 485 GREEN, 10 KEPT | ✅ | feature/portfolio/plan-constraints |
| M3 S16 | UI/API 마무리: Sortino·Calmar 메트릭 카드, /portfolio/rebalance 제약 파라미터, 골든 케이스 Sortino/Calmar 회귀. 490 GREEN, 10 KEPT | ✅ | feature/ui/metrics-and-constraints |
| M4 S1 | /similar strategy 스위치 (weighted_sum/spearman/cointegration) + 탐색 UI 셀렉트 + CLAUDE.md L3 매핑 정정. 493 GREEN, 10 KEPT | ✅ | feature/similarity/strategy-switch |
| M4 S2 | /backtest/pair/{a}/{b}/walk-forward 엔드포인트 — split_ratio 단일 분할 IS/OOS 백테스트. 495 GREEN, 10 KEPT | ✅ | feature/backtest/walk-forward |
| M4 S3 | POST /backtest/batch — 다중 페어 배치 백테스트 + 평균 집계. 497 GREEN, 10 KEPT | ✅ | feature/backtest/batch |
| M4 S4 | Walk-forward IS/OOS UI 토글 + /batch 페이지 신설 (페어 add/remove, 집계 카드, 결과 테이블). 497 GREEN, 10 KEPT | ✅ | feature/ui/walk-forward-and-batch (main `e66fc7f`) |
| M4 S6 | /batch 정렬/필터(실패 숨김) + CSV 내보내기 | ✅ | feature/backtest/walk-forward-kfold |
| M4 S5 | /backtest/pair/{a}/{b}/walk-forward-kfold — folds=k, k-1 rolling 폴드 + IS/OOS 평균 집계. 499 GREEN, 10 KEPT | ✅ | feature/backtest/walk-forward-kfold |
| M5 S1 | ADR-006 + risk 도메인 값 객체 (PositionSnapshot, RiskContext, Allow/BlockNew/ForceClose). 515 GREEN, 10 KEPT | ✅ | feature/risk/domain-value-objects |
| M5 S2 | RiskGuard 포트 + EvaluateRisk 유스케이스 (체인 평가, 보수적 우선, 다중 ForceClose 병합). 520 GREEN, 10 KEPT | ✅ | feature/risk/evaluate-use-case |
| M5 S3 | PositionLimitGuard (G1) — 단일 심볼 max_weight 한도 + 경계값 3종 + 기존/후보 합산 검사. 529 GREEN, 10 KEPT | ✅ | feature/risk/position-limit-guard |
| M5 S4 | DrawdownCircuitBreaker (G3) — peak 대비 누적 DD 한도 초과 시 BlockNew, 후보 없으면 Allow. 536 GREEN, 10 KEPT | ✅ | feature/risk/drawdown-circuit-breaker |
| M5 S5 | StopLossGuard (G2) — 포지션 손실률 한도 초과 시 ForceClose. 541 GREEN, 10 KEPT | ✅ | feature/risk/stop-loss-guard |
| M5 S6 | DailyLossLimitGuard (G4) — 당일 손익률 한도 이하 시 BlockNew. 549 GREEN, 10 KEPT | ✅ | feature/risk/daily-loss-limit |
| M5 S7 | import-linter `risk hexagonal layers` + `risk purity` 2 계약 추가 (10→12 KEPT) + ADR-005 갱신 | ✅ | feature/risk/importlinter-contracts |
| M5 S8/S9 | backtest 통합 — EntryFilter 포트 + RunBacktest 훅 주입 + RiskEntryFilter 어댑터 (risk 가드 브릿지). 기본 None 으로 골든 수치 불변. 555 GREEN, 12 KEPT | ✅ | feature/backtest/risk-integration |
| M5 S12 | /backtest/pair `risk_position_limit/max_drawdown/daily_loss` 쿼리 + InMemoryBacktestEngine.entry_filter 주입 + config 에코. 557 GREEN, 12 KEPT | ✅ | feature/api/risk-params |
| M5 S13 | 백테스트 대시보드 — 접이식 "리스크 가드 (선택)" 섹션 + 3 입력 (포지션/DD/일일손실), 빈값=null → 쿼리 미포함. 557 GREEN, 12 KEPT | ✅ | feature/web/risk-inputs |

### 🔴 블로커
없음

### 미완료 (다음 작업 순서) ⏳

| 우선순위 | 슬라이스 | 설명 | 브랜치 |
|---------|---------|------|--------|
| 1 | M5 계획 | `/plan` 으로 리스크 관리 vs 실시간 데이터 파이프라인 브레인스토밍 | - |
| 2 | M4 S7 | k-fold UI (folds 입력 + 폴드별 카드 표시) | `feature/web/walk-forward-kfold-ui` |

상세 계획: [`docs/plans/M2-plan.md`](docs/plans/M2-plan.md)
M1 회고: [`docs/retros/M1-retrospective.md`](docs/retros/M1-retrospective.md)

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
- **L3** (`portfolio`, `trading_signal`, `backtest`, `trading`, `risk`):
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
