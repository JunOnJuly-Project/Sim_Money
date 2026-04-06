# Sim_Money 핸드오프 문서

> 다른 PC / 다른 세션에서 이 프로젝트를 **끊김 없이 이어서 진행**하기 위한 안내서.
> 스키마 버전: v2
> 최종 업데이트: 2026-04-07

---

## 1. 프로젝트 개요

**Sim_Money** — 비슷하거나 정반대의 유형/등락/경향을 보이는 주식들을 찾아주는 웹앱.

- **대상**: 상관관계 기반으로 종목을 탐색하려는 개인 투자자
- **스택**: 미정 (후보: Next.js + TypeScript + Python(FastAPI) + DuckDB/Postgres)
- **방법론**: 미정 — `/plan` 단계에서 결정

상세 계획서: [`docs/plans/Sim_Money-plan.md`](docs/plans/)

---

## 2. 다른 PC에서 이어 받기

### 2-1. 필수 도구

| 도구 | 버전 | 용도 |
|---|---|---|
| Git | 2.40+ | 소스 클론 |
| Node.js | 20+ | 프론트엔드 (예정) |
| Python | 3.11+ | 데이터/백엔드 (예정) |

### 2-2. 클론 및 시크릿

```bash
git clone {repo-url}
cd Sim_Money
cp .env.example .env
# 시크릿 채우기
```

### 2-3. 실행

```bash
# 추후 정의
```

### 2-4. 동작 확인 (smoke test)

```bash
# 추후 정의
```

---

## 3. 현재 진행 상태

### 현재 브랜치
`main`

### 완료 ✅

| Phase | 이슈 | 상태 | 브랜치 |
|---|---|---|---|
| Phase 0 | init | ✅ 뼈대 생성 | main |

### 🔴 블로커
없음

### 미완료 (다음 작업 순서) ⏳
1. `/plan Sim_Money` — 요구사항 정리, 데이터 소스 선정, 유사도 알고리즘 후보 결정
2. 스택 확정 및 `.env.example` 보강
3. Phase 1 구현 착수

### 알려진 미해결 이슈 / 주의사항
- [ ] 주가 데이터 소스 라이선스 검토 필요 (yfinance / KRX / Alpha Vantage 등)

---

## 4. 방법론 강제 규칙

`/plan` 단계에서 결정. 잠정: L1 (프로토타입).

---

## 5. 재개 체크리스트

새 세션에서 Claude 에게 다음을 먼저 실행하게 하라:

1. 이 문서(`HANDOFF.md`) 전체 읽기
2. `/bootstrap` 실행 (정합성 게이트)
3. `git log --oneline --all --graph | head -30` 확인
4. 블로커가 있으면 먼저 해결
5. 아니면 "미완료" 섹션의 다음 우선순위 작업 시작

---

## 6. 참고 자료

- 계획서: `docs/plans/`
- CI: `.github/workflows/ci.yml`
- 전역 지침: `~/.claude/CLAUDE.md`
