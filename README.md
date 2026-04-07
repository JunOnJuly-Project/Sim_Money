# Sim_Money

비슷하거나 정반대의 유형 · 등락 · 경향을 보이는 주식들을 찾아주는 웹앱.

## 빠른 시작

새 세션 / 다른 PC 에서 이어받으려면 [`HANDOFF.md`](HANDOFF.md) 를 먼저 읽으세요.

### Docker Compose 로 전체 스택 실행

```bash
# 최초 실행 — 이미지 빌드 포함
docker compose up --build

# 이후 실행
docker compose up
```

| 서비스 | URL | 설명 |
|--------|-----|------|
| Web (Next.js) | http://localhost:3000 | 유사도 플레이그라운드 UI |
| API (FastAPI) | http://localhost:8000/docs | REST API + Swagger UI |
| API 헬스 체크 | http://localhost:8000/health | `{"status": "ok"}` |

환경변수 (선택 재정의):

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DUCKDB_PATH` | `/data/sim_money.duckdb` | DuckDB 파일 경로 |
| `SEED_TICKERS` | `KRX:005930,KRX:000660` | M1 플레이스홀더 유니버스 종목 |

## 문서

- [핸드오프](HANDOFF.md)
- [계획서](docs/plans/)
- [CI](.github/workflows/ci.yml)
