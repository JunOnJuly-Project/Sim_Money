# M2 계획서 (Milestone 2)

- **기간**: W5 ~ W12 (8주, 2026-04-08 ~ 2026-06-02 추정)
- **목표**: 백테스트 엔진 + 추가 유사도 전략 + 페이퍼 트레이딩 기반 구축
- **엔드게임 연결**: M2 종료 시 법률 검토 1차 게이트 (투자자문/일임 판단) 통과 후 Stage 2 진입 여부 결정

---

## Epic 분해

### Epic 1 — L2 similarity 확장 (W5~W6)

| 슬라이스 | 설명 | 레벨 |
|---------|------|------|
| S1 | `SpearmanStrategy` 포트 구현 + 골든 회귀 테스트 | L2 |
| S2 | `CointegrationStrategy` (Engle-Granger) 포트 구현 | L2 |
| S3 | `DTWStrategy` (Dynamic Time Warping) 포트 구현 | L2 |
| S4 | `StrategyRegistry` — 전략 동적 선택 + API 파라미터 연동 | L2 |

- 모든 전략은 기존 `SimilarityStrategy` 포트 구현체로 추가. 인터페이스 변경 금지.
- 커버리지 기준: 80%+

### Epic 2 — L3 backtest 엔진 (W6~W9)

| 슬라이스 | 설명 | 레벨 |
|---------|------|------|
| S1 | `PriceBar` 도메인 값 객체 (OHLCV, 불변식) | L3 |
| S2 | `Strategy` 인터페이스 포트 (Signal 도메인 의존) | L3 |
| S3 | `BacktestEngine` 유스케이스 (포트/어댑터, 이벤트 루프) | L3 |
| S4 | `PerformanceMetrics` — 샤프 비율 / MDD / 승률 계산 | L3 |
| S5 | `BacktestRepository` 포트 + DuckDB 어댑터 | L3 |

- **L3 엄격도 즉시 발동**: 첫 로직 커밋부터 90% 커버리지, 단일 에이전트 금지, `/team-develop` 필수.
- 커밋 순서: 포트 정의 → 실패 테스트 → 유스케이스 구현 → 어댑터 구현 → 통합 테스트.

### Epic 3 — L3 signal (W8~W10)

| 슬라이스 | 설명 | 레벨 |
|---------|------|------|
| S1 | `PairTradingSignal` — 공적분 기반 mean reversion Z-score | L3 |
| S2 | `SignalPort` 포트 + `InMemorySignalRepository` Fake | L3 |
| S3 | `GenerateSignals` 유스케이스 | L3 |

- 실거래 신호 생성 로직 아님 — 백테스트 내부 시뮬레이션 전용.

### Epic 4 — L3 portfolio 스켈레톤 (W9~W10)

| 슬라이스 | 설명 | 레벨 |
|---------|------|------|
| S1 | `PositionSizer` 포트 + `FixedFractionSizer` 1개 구현 | L3 |
| S2 | `RebalancingPolicy` 포트 (스켈레톤) | L3 |

- 실거래 로직 0줄 유지. Stage 3 법률 게이트 통과 전까지 구현 금지.

### Epic 5 — 페이퍼 트레이딩 driver (W10~W11)

| 슬라이스 | 설명 | 레벨 |
|---------|------|------|
| S1 | `SimulatedAccount` — 시뮬레이션 계좌 잔고/포지션 | L2 |
| S2 | 체결/수수료/슬리피지 가드 (파라미터화) | L2 |
| S3 | `PaperTradingDriver` — 실시간 가격 구독 없이 tick replay | L2 |

### Epic 6 — 웹 대시보드 확장 (W11~W12)

| 슬라이스 | 설명 | 레벨 |
|---------|------|------|
| S1 | 백테스트 실행 UI (전략/기간 선택 폼) | L1 |
| S2 | 결과 대시보드 (샤프/MDD/누적수익 차트) | L1 |
| S3 | 전략 비교 테이블 (WeightedSum / Spearman / Cointegration) | L1 |

---

## 일정 요약

| 주차 | 주요 산출물 |
|------|-----------|
| W5 | SpearmanStrategy + CointegrationStrategy |
| W6 | DTWStrategy + BacktestEngine 포트 정의 |
| W7 | BacktestEngine 구현 + PriceBar |
| W8 | PerformanceMetrics + PairTradingSignal 포트 |
| W9 | GenerateSignals + Portfolio 스켈레톤 |
| W10 | PaperTradingDriver |
| W11 | 웹 대시보드 기초 |
| W12 | 통합 smoke + M2 회고 + 법률 검토 게이트 |

---

## 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| 생존편향 | 백테스트 과대평가 | KRX 상장폐지 이력 실데이터 도입 (M2 S1) |
| 과적합 | 전략 파라미터 최적화 환상 | Walk-forward 검증 필수, 파라미터 고정 우선 |
| Lookahead bias | 미래 데이터 누수 | `PriceBar` 불변식 + 날짜 인덱스 단방향 이터레이션 강제 |
| 거래비용 모델링 미흡 | 실제 수익률과 괴리 | 슬리피지/수수료 파라미터 명시, 기본값 보수적 설정 |
| L3 단일 에이전트 오염 | 아키텍처 붕괴 | CI pre-commit 훅 + PR 체크리스트 강제 |

---

## M2 종료 게이트

- [ ] 161개 기존 테스트 모두 GREEN 유지
- [ ] L3 도메인 커버리지 90%+
- [ ] import-linter 계약 3 KEPT 이상
- [ ] 백테스트 결과 대시보드 smoke 통과
- [ ] **법률 검토 1차**: 투자자문업/투자일임업/금융투자업 해당 여부 확인 후 Stage 2 진입 여부 결정
