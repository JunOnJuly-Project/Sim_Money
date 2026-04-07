# Sim_Money 개발 계획서

> 최종 업데이트: 2026-04-07
> 상태: Phase 0 완료, M1 W1 진입 준비

---

## 1. 제품 개요

### 엔드게임 선언
**Sim_Money 는 1년 내 개인 전용 실거래·자동매매 시스템으로 수렴한다.**
유사도 탐색 웹앱은 이 여정의 Stage 1 이며, 단독 제품이 아니다. 모든 M1 의사결정은
Stage 3(실거래) 경로를 막지 않는 것을 최우선 제약으로 삼는다.

### 3단 로켓
| 단계 | 기간 | 목표 |
|---|---|---|
| **Stage 1 (MVP)** | 3~4주 | 주식 유사도 탐색 + 공식 플레이그라운드 UI. 매일 쓰고 싶은 탐색 도구. |
| **Stage 2** | 3~6개월 | 백테스트 엔진, 공적분(Engle-Granger), 신호 생성, 페이퍼 트레이딩. |
| **Stage 3** | 6~12개월 | 한국투자증권 오픈API 연동, 소액 실거래 → 본격 운용 확장. |

---

## 2. 사용자 범위 · 법적 트랙

- **사용자**: 본인 1인 전용. 제3자에게 배포·공개하지 않는다(아이디어 공유는 허용).
- **법률 검토 게이트**: Stage 3(실거래) 진입 이전에 반드시 수행.
  - 투자자문업/투자일임업/금융투자업 해당 여부
  - 개인 자동매매 법적 경계
  - 한국투자증권 오픈API 이용약관
- **고지 문구**: 모든 UI 화면에 "본 도구는 개인 사용 목적이며 투자 권유가 아닙니다" 상시 표시.

---

## 3. 대상 시장 · 자본 · 매매 스타일

- **시장**: 전 시장 지향. MVP 는 KOSPI200 + S&P500 (~700 종목). 이후 KOSDAQ, 유럽, 일본 확장.
- **자본 규모**: Stage 3 초기에는 소액(손실 허용 범위). 검증 후 점진 확장.
- **매매 스타일**: Strategy 패턴으로 교체 가능.
  - `PairsTradingStrategy` / `MeanReversionStrategy` / `MomentumStrategy` / `RebalanceStrategy`
  - MVP 는 전략 로직 없이 인터페이스 스켈레톤만.

---

## 4. 도메인 엄격도 L1/L2/L3 매핑

| 레벨 | 도메인 | M1 에서의 상태 |
|---|---|---|
| **L3** (Clean Arch + ArchUnit + 90% 커버리지) | `portfolio/`, `signal/`, `backtest/`, `trading/`, `risk/` | **스켈레톤만**. 로직 0. 패키지·인터페이스 껍데기. |
| **L2** (DDD 애그리거트 + 80% 커버리지) | `similarity/`, `market_data/`, `universe/` | M1 핵심. 구현 대상. |
| **L1** (프로토타입 허용) | `ui_playground/`, `visualization/`, `notebooks/`, `fixtures/`, `docs/` | M1 핵심. 빠르게 반복. |

- **의존 방향**: L1 → L2 허용, L1/L2 → L3 **금지**, L3 → L2 허용.
- **강제 수단**: `import-linter` 로 CI 에서 검증.
- **레벨 승격 트리거**: L3 스켈레톤에 실제 로직이 한 줄이라도 추가되는 순간 L3 엄격도 즉시 발동
  (테스트 커버리지 90%, ArchUnit, 단일 에이전트 금지).

---

## 5. 아키텍처 원칙

- **Clean Architecture + Strategy 패턴**. 공식·매매스타일·데이터소스 전부 교체 가능해야 한다.
- **인터페이스 우선**:
  - `SimilarityStrategy` (M1 구현: `WeightedSumStrategy`)
  - `MarketDataSource` (M1 구현: `FinanceDataReaderSource`)
  - `TradingStrategy`, `KillSwitch` (M1 빈 껍데기)
- **M1 도메인 모델**: `Ticker`, `Return`, `Price`, `CorrelationMatrix`
- **스켈레톤 도메인 모델**: `Portfolio`, `Position`, `Signal`, `Order`, `Trade`, `Risk`
- **의존성 주입**: 전략은 config/DI 로 주입. UI 슬라이더는 전략 파라미터를 일반적 key-value 로 노출.

---

## 6. 스택 & Docker-compose

| 계층 | 기술 |
|---|---|
| Backend | Python 3.11+, FastAPI, DuckDB, FinanceDataReader, pandas, numpy, scipy |
| Frontend | Next.js 15+, TypeScript, shadcn/ui, recharts 또는 visx, KaTeX |
| Test | pytest, hypothesis, import-linter |
| 배포 | Docker-compose (web / api / db / batch) |

### Docker-compose 서비스
- `web`: Next.js (port 3000)
- `api`: FastAPI (port 8000)
- `db`: DuckDB 파일 볼륨 마운트 (단일 파일 DB)
- `batch`: 일배치 데이터 파이프라인 (cron/APScheduler)

---

## 7. MVP 유사도 공식

```
score(A,B) = sign(ρ_p) · ( w₁·|ρ_p| + w₂·shape + w₃·stability )

전처리:
  - 수정주가 기반 로그수익률
  - N ≥ 252 거래일
  - σ(logret) ≥ 1e-6
  - 거래정지 NaN 마스킹 (비율 > 5% 제외)
  - 유니버스 스냅샷 기준일 T 고정

신호:
  ρ_p       = pearson(logret_A, logret_B)
  shape     = clip(1 − std(rolling_corr_W), 0, 1)       # 기본 W=60
  stability = clip(1 − 2·std(ρ_k), 0, 1)                # 기본 k=3 구간 분할

필터: |ρ_p| ≥ 0.1, TopK(ρ_p,150) ∪ BottomK(ρ_p,150)
가중치: w₁/w₂/w₃ 기본 0.5/0.3/0.2, 슬라이더 조정 (합=1 자동 정규화)

출력:
  similar  Top N = score DESC, sign=+1
  opposite Top N = score ASC,  sign=−1

NaN/Inf 가드, sign(0)→+1, 결과에서 명시 제외
```

---

## 8. Phase 2+ 백로그 (연기, UI 토글로 노출)

- Spearman/Kendall 상관 병기
- Mantegna 거리 √(2(1−ρ))
- Engle-Granger 공적분, rolling ADF
- DTW (dtaidistance + Sakoe-Chiba band)
- 리드-래그 시차 상관
- DCC-GARCH 동적 상관
- 백테스트 엔진 (수수료·슬리피지·리밸런싱)
- 페이퍼 트레이딩 → 실거래(한투 오픈API)

---

## 9. M1 스코프 체크리스트

### ✅ M1 에서 만든다
- [ ] 데이터 파이프라인: FinanceDataReader 기반, 수정주가 로그수익률, DuckDB 적재, 일배치
- [ ] 유니버스: KOSPI200 + S&P500, 생존편향 공시, 유니버스 스냅샷 고정
- [ ] `SimilarityStrategy` 인터페이스 + `WeightedSumStrategy` 구현
- [ ] ρ 행렬 precompute + 1차 필터
- [ ] FastAPI 조회 엔드포인트 (검색, Top N similar/opposite)
- [ ] 공식 플레이그라운드 UI: 슬라이더(w1/w2/w3, W, k, |ρ|필터), LaTeX 실시간 수식, 실시간 랭킹
- [ ] 시각화: 산점도+회귀선, rolling ρ 차트, 정규화 가격 중첩 차트
- [ ] Docker-compose (web / api / db / batch)
- [ ] 개인 사용 고지 문구
- [ ] 골든 회귀 테스트 전부 GREEN

### ⏸️ M1 에서 만들지 않는다 (빈 도메인 경계만)
- [ ] `portfolio/`, `signal/`, `backtest/`, `trading/`, `risk/` 패키지 + 인터페이스 껍데기
- [ ] `KillSwitch` 인터페이스 빈 선언
- [ ] `import-linter` 계약: L1/L2 → L3 금지 강제

---

## 10. 에픽·스토리·태스크 분해

### Epic 1: 데이터 파이프라인 & 유니버스 (L2) — W1
**목표**: 700 종목 일봉이 DuckDB 에 들어와 있고 로그수익률이 준비되어 있다.

- **Story 1.1**: `MarketDataSource` 포트 정의
  - Task 1.1.1: `market_data/ports/market_data_source.py` 인터페이스 작성
  - Task 1.1.2: `Ticker`, `Price`, `Return` 값 객체 정의
  - 수용기준: `fetch(ticker, start, end) -> DataFrame[date, adj_close]` 시그니처, 타입힌트 완비, 단위테스트 스텁.
- **Story 1.2**: FinanceDataReader 어댑터
  - Task 1.2.1: `FinanceDataReaderSource` 구현
  - Task 1.2.2: 재시도/타임아웃/레이트리밋 처리
  - Task 1.2.3: NaN/거래정지 마스킹 로직
  - 수용기준: KOSPI200 전 종목 1년치 1회 fetch 성공, 5% 초과 결측 종목 자동 제외.
- **Story 1.3**: 유니버스 관리
  - Task 1.3.1: KOSPI200/S&P500 티커 리스트 스냅샷 고정 (기준일 T)
  - Task 1.3.2: 생존편향 공시 문서화 (`docs/universe-bias.md`)
  - 수용기준: 스냅샷 JSON 커밋, 기준일 명시.
- **Story 1.4**: DuckDB 적재 + 일배치
  - Task 1.4.1: 스키마 설계 (`prices`, `returns`, `universe`)
  - Task 1.4.2: upsert 로직
  - Task 1.4.3: APScheduler 일배치 러너
  - 수용기준: `python -m batch.daily` 실행 시 전 종목 갱신, 중복 적재 없음.

### Epic 2: 유사도 엔진 — WeightedSum (L2) — W2
**목표**: 골든 회귀 테스트 GREEN.

- **Story 2.1**: `SimilarityStrategy` 포트 + 공용 모델
  - Task 2.1.1: 인터페이스 (`compute(a, b, params) -> Score`)
  - Task 2.1.2: `CorrelationMatrix` 값 객체
  - 수용기준: 교체 가능성을 증명하는 더미 전략 테스트 통과.
- **Story 2.2**: 전처리 게이트
  - Task 2.2.1: N ≥ 252, σ ≥ 1e-6, NaN 비율 검사
  - Task 2.2.2: hypothesis 속성 테스트 PBT-01~03
  - 수용기준: 엣지 케이스 커버, 부적격 쌍 제외 확인.
- **Story 2.3**: `WeightedSumStrategy` 구현
  - Task 2.3.1: ρ_p, shape, stability 계산
  - Task 2.3.2: sign·가중합·정규화
  - Task 2.3.3: NaN/Inf 가드
  - 수용기준: 골든 테스트 T-REG-01~05 GREEN.
- **Story 2.4**: ρ 행렬 precompute + 필터
  - Task 2.4.1: 700x700 상관 행렬 배치 계산
  - Task 2.4.2: TopK/BottomK 필터
  - 수용기준: 전체 계산 60초 이내, DuckDB 캐시.

### Epic 3: 조회 API (L1~L2) — W3
- **Story 3.1**: FastAPI 부트스트랩 + 헬스체크
- **Story 3.2**: `GET /search?q={ticker}` — 유니버스 검색
- **Story 3.3**: `GET /similar/{ticker}?n=20` — Top N similar
- **Story 3.4**: `GET /opposite/{ticker}?n=20` — Top N opposite
- **Story 3.5**: `POST /score` — 슬라이더 파라미터로 재계산
- 수용기준: OpenAPI 문서 자동 생성, 응답 500ms 이내, CORS 허용.

### Epic 4: 공식 플레이그라운드 UI (L1) — W3~W4
- **Story 4.1**: Next.js 부트스트랩 + shadcn/ui 설치
- **Story 4.2**: 검색 + 기본 탐색 화면
- **Story 4.3**: 슬라이더 패널 (w1/w2/w3, W, k, |ρ|필터)
- **Story 4.4**: KaTeX 실시간 수식 렌더
- **Story 4.5**: 슬라이더 변경 → 디바운스 → `/score` 호출 → 랭킹 갱신
- **Story 4.6**: 개인 사용 고지 문구 배너
- 수용기준: 슬라이더 드래그 시 수식과 랭킹이 300ms 이내 갱신, 모바일 레이아웃 깨지지 않음.

### Epic 5: 시각화 (L1) — W4
- **Story 5.1**: 산점도 + 회귀선 (logret_A vs logret_B)
- **Story 5.2**: rolling ρ 시계열 차트
- **Story 5.3**: 정규화 가격 중첩 차트
- 수용기준: 세 차트가 선택 쌍에 반응, tooltip 상호작용.

### Epic 6: 배포 & 운영 (L1) — W4
- **Story 6.1**: Dockerfile (web, api, batch)
- **Story 6.2**: docker-compose.yml + 볼륨 + 네트워크
- **Story 6.3**: `.env.example`, README 실행 가이드
- **Story 6.4**: 로컬 스모크 테스트 스크립트
- 수용기준: `docker compose up` 한 방에 전부 기동, 첫 요청 성공.

### Epic 7: L3 도메인 스켈레톤 & 아키텍처 경계 강제 (L3 빈 껍데기) — W1 병행
- **Story 7.1**: `portfolio/`, `signal/`, `backtest/`, `trading/`, `risk/` 패키지 생성
- **Story 7.2**: 각 도메인 포트 인터페이스 빈 선언 (`KillSwitch`, `OrderGateway` 등)
- **Story 7.3**: `import-linter` 계약 파일 (`.importlinter`)
- **Story 7.4**: CI 에 import-linter 단계 추가
- 수용기준: L1/L2 에서 L3 import 시도 시 CI 레드, 통과 시 그린.

---

## 11. 골든 회귀 테스트 명세

| ID | 내용 | 기대 |
|---|---|---|
| T-REG-01 | KODEX200 ↔ TIGER200 | score ≥ 0.95 |
| T-REG-02 | KODEX레버리지 ↔ KODEX인버스 | score ≤ −0.70 |
| T-REG-03 | 전 쌍 | score ∈ [−1, 1] |
| T-REG-04 | 무상관 쌍 (합성 데이터) | `score` < 0.15 |
| T-REG-05 | sign 보존 (ρ_p 부호 = score 부호) | 100% |
| PBT-01 | N < 252 → 부적격 | hypothesis |
| PBT-02 | σ < 1e-6 → 부적격 | hypothesis |
| PBT-03 | NaN 비율 > 5% → 부적격 | hypothesis |

---

## 12. 알려진 한계 (ADR-002 에도 기록)

1. **상관관계 ≠ 공적분**: mean-reversion 보장 없음. 투자 판단의 근거 아님.
2. **체제변화(regime change) 취약**: 과거 상관이 미래를 보장하지 않음.
3. **가중치 경험적**: 백테스트 전이므로 w1/w2/w3 는 직관적 값.
4. **shape/stability 중복 가능성**: 시간 스케일만 다른 동일 정보일 수 있음. Phase 2 에서 재설계.
5. **Pearson 단독**: Spearman, 공적분 등은 Phase 2+.
6. **생존편향 부분 제거**: 스냅샷 공시만, 완전 제거 아님.

---

## 13. 리스크 · 완화

| 리스크 | 영향 | 완화 |
|---|---|---|
| yfinance 차단/레이트리밋 | 데이터 파이프라인 중단 | FinanceDataReader 우선, `MarketDataSource` 포트로 공급자 교체 가능 |
| 데이터 라이선스 | 법적 리스크 | KRX/FDR 약관 문서화, 상업 재배포 금지 명시 |
| 법적 리스크 (실거래) | Stage 3 블로킹 | Stage 3 전 법률 검토 게이트 필수 |
| 운영 모니터링 부재 | 실거래 사고 | `KillSwitch` 인터페이스 M1 에 선언, Stage 2 구현 |
| 스코프 크립 | M1 지연 | M1 체크리스트 외 전부 Phase 2+ 백로그로 강제 이관 |
| 상관 해석 오남용 | 잘못된 매매 | UI 고지 문구 상시 + 한계 문서 링크 |

---

## 14. 마일스톤

| 마일스톤 | 기간 | 산출물 |
|---|---|---|
| **M1 W1** | 1주차 | 데이터 파이프라인 + 유니버스 + L3 스켈레톤 |
| **M1 W2** | 2주차 | similarity 엔진 + 골든 테스트 GREEN |
| **M1 W3** | 3주차 | FastAPI + Next.js 기본 탐색 |
| **M1 W4** | 4주차 | 플레이그라운드 UI + 시각화 + docker-compose |
| **M2** | +1개월 | Spearman/공적분/DTW 전략 추가 (Strategy 확장) |
| **M3** | +2개월 | 백테스트 엔진 |
| **M4** | +3개월 | 신호 생성 + 페이퍼 트레이딩 |
| **M5** | +6개월 | 법률 검토 게이트 통과 |
| **M6** | +9개월 | 한국투자증권 오픈API 연동, 소액 실거래 |
| **M7** | +12개월 | 본격 운용 + 모니터링/KillSwitch 완비 |

---

## 15. ADR 링크

- [ADR-000: 프로젝트 엔드게임](../adr/ADR-000-endgame.md)
- [ADR-001: 도메인 엄격도 매핑](../adr/ADR-001-domain-levels.md)
- [ADR-002: 유사도 Strategy 패턴](../adr/ADR-002-similarity-strategy-pattern.md)
