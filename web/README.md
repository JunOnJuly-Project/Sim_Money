# Sim Money Web — 유사 종목 탐색 UI

개인 전용 실험 프론트엔드. Next.js 15 + TypeScript + Tailwind CSS 4.

> 본 도구는 개인 전용 실험이며 투자 조언이 아닙니다.

## 실행 방법

### 1. 의존성 설치

```bash
cd web
npm install
```

### 2. 개발 서버 시작

```bash
npm run dev
```

브라우저에서 [http://localhost:3000](http://localhost:3000) 접속.

### 3. 백엔드 서버 실행 (필수)

프론트엔드는 `/api/*` 요청을 `http://localhost:8000` 으로 프록시한다.
백엔드 FastAPI 서버를 먼저 실행해야 실제 유사도 결과를 받을 수 있다.

```bash
# 프로젝트 루트에서
cd ..
python -m uvicorn src.sim_money.main:app --reload --port 8000
```

백엔드가 없는 경우 탐색 버튼 클릭 시 오류 메시지가 표시된다.

## 폴더 구조

```
web/
├── app/
│   ├── globals.css      # 전역 스타일 + CSS 변수
│   ├── layout.tsx       # 루트 레이아웃
│   └── page.tsx         # 탐색 메인 페이지
├── next.config.ts       # API 프록시 설정
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

## API 연동

| 엔드포인트 | 설명 |
|---|---|
| `GET /api/similar/{symbol}` | 유사 종목 탐색 |

쿼리 파라미터: `market`, `universe`, `as_of`, `top_k`

응답 형식:
```json
[
  { "rank": 1, "ticker": "000660", "score": 0.9312 },
  ...
]
```
