"use client";

import { useState, FormEvent } from "react";

// ── 타입 정의 ──────────────────────────────────────────────────────────────

type Market = "KRX" | "NASDAQ";

/** 백엔드 /similar/{symbol} 응답의 단일 결과 항목 */
interface SimilarItem {
  rank: number;
  ticker: string;
  score: number;
}

/** 백엔드 /similar/{symbol} 의 응답 스키마 */
interface SimilarResponse {
  target: string;
  results: Array<{ ticker: string; score: number }>;
}

/** 탐색 폼의 입력 상태 */
interface SearchForm {
  market: Market;
  symbol: string;
  universe: string;
  as_of: string;
  top_k: number;
}

// ── 상수 ──────────────────────────────────────────────────────────────────

const DEFAULT_UNIVERSE = "KOSPI200";
const DEFAULT_TOP_K = 10;
const SCORE_DECIMAL_PLACES = 4;

/** 오늘 날짜를 YYYY-MM-DD 형태로 반환한다 (기본 as_of 값) */
function getTodayString(): string {
  return new Date().toISOString().slice(0, 10);
}

/** 유사도 공식 plain-text 표현 (KaTeX 는 이후 슬라이스에서 적용 예정) */
const SIMILARITY_FORMULA =
  "score = w1*return_corr + w2*volume_corr + w3*sector_match";

// ── 서브 컴포넌트: 경고 배너 ───────────────────────────────────────────────

function DisclaimerBanner() {
  return (
    // ADR-000: 개인 전용 고지 문구는 반드시 상단에 표시해야 한다.
    <div
      className="w-full rounded-md border px-4 py-2 text-sm text-center"
      style={{
        borderColor: "var(--muted)",
        color: "var(--muted)",
        backgroundColor: "var(--card-bg)",
      }}
    >
      본 도구는 개인 전용 실험이며 투자 조언이 아닙니다.
    </div>
  );
}

// ── 서브 컴포넌트: 탐색 폼 ────────────────────────────────────────────────

interface SearchFormProps {
  form: SearchForm;
  isLoading: boolean;
  onChange: (updated: Partial<SearchForm>) => void;
  onSubmit: (e: FormEvent) => void;
}

function ExploreForm({ form, isLoading, onChange, onSubmit }: SearchFormProps) {
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      {/* 마켓 선택 */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
          마켓
        </label>
        <select
          value={form.market}
          onChange={(e) => onChange({ market: e.target.value as Market })}
          className="rounded-md border px-3 py-2 text-sm"
          style={{
            backgroundColor: "var(--card-bg)",
            borderColor: "var(--border)",
            color: "var(--foreground)",
          }}
        >
          <option value="KRX">KRX (한국거래소)</option>
          <option value="NASDAQ">NASDAQ</option>
        </select>
      </div>

      {/* 심볼 입력 */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
          심볼 (예: 005930, AAPL)
        </label>
        <input
          type="text"
          required
          placeholder="종목 코드를 입력하세요"
          value={form.symbol}
          onChange={(e) => onChange({ symbol: e.target.value.trim() })}
          className="rounded-md border px-3 py-2 text-sm"
          style={{
            backgroundColor: "var(--card-bg)",
            borderColor: "var(--border)",
            color: "var(--foreground)",
          }}
        />
      </div>

      {/* 유니버스 입력 */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
          유니버스
        </label>
        <input
          type="text"
          required
          value={form.universe}
          onChange={(e) => onChange({ universe: e.target.value.trim() })}
          className="rounded-md border px-3 py-2 text-sm"
          style={{
            backgroundColor: "var(--card-bg)",
            borderColor: "var(--border)",
            color: "var(--foreground)",
          }}
        />
      </div>

      {/* 기준일 */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
          기준일 (as_of)
        </label>
        <input
          type="date"
          required
          value={form.as_of}
          onChange={(e) => onChange({ as_of: e.target.value })}
          className="rounded-md border px-3 py-2 text-sm"
          style={{
            backgroundColor: "var(--card-bg)",
            borderColor: "var(--border)",
            color: "var(--foreground)",
          }}
        />
      </div>

      {/* top_k */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
          상위 결과 수 (top_k)
        </label>
        <input
          type="number"
          min={1}
          max={100}
          required
          value={form.top_k}
          onChange={(e) => onChange({ top_k: Number(e.target.value) })}
          className="rounded-md border px-3 py-2 text-sm"
          style={{
            backgroundColor: "var(--card-bg)",
            borderColor: "var(--border)",
            color: "var(--foreground)",
          }}
        />
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="rounded-md px-4 py-2 text-sm font-semibold transition-opacity disabled:opacity-50"
        style={{
          backgroundColor: "var(--accent)",
          color: "#0f172a",
        }}
      >
        {isLoading ? "탐색 중..." : "유사 종목 탐색"}
      </button>
    </form>
  );
}

// ── 서브 컴포넌트: 결과 테이블 ────────────────────────────────────────────

interface ResultTableProps {
  items: SimilarItem[];
}

/** 점수가 양수면 초록 배지, 음수면 빨간 배지를 반환한다 */
function ScoreBadge({ score }: { score: number }) {
  const isPositive = score >= 0;
  return (
    <span
      className="rounded px-2 py-0.5 text-xs font-medium"
      style={{
        backgroundColor: isPositive ? "rgba(74,222,128,0.15)" : "rgba(248,113,113,0.15)",
        color: isPositive ? "var(--success)" : "var(--danger)",
      }}
    >
      {isPositive ? "양" : "음"}
    </span>
  );
}

function ResultTable({ items }: ResultTableProps) {
  if (items.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-md border" style={{ borderColor: "var(--border)" }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ backgroundColor: "var(--card-bg)", borderBottom: `1px solid var(--border)` }}>
            <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--muted)" }}>
              순위
            </th>
            <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--muted)" }}>
              티커
            </th>
            <th className="px-4 py-3 text-right font-medium" style={{ color: "var(--muted)" }}>
              유사도 점수
            </th>
            <th className="px-4 py-3 text-center font-medium" style={{ color: "var(--muted)" }}>
              방향
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.ticker}
              className="border-t"
              style={{ borderColor: "var(--border)" }}
            >
              <td className="px-4 py-3 font-mono" style={{ color: "var(--muted)" }}>
                {item.rank}
              </td>
              <td className="px-4 py-3 font-semibold" style={{ color: "var(--foreground)" }}>
                {item.ticker}
              </td>
              <td className="px-4 py-3 text-right font-mono" style={{ color: "var(--accent)" }}>
                {item.score.toFixed(SCORE_DECIMAL_PLACES)}
              </td>
              <td className="px-4 py-3 text-center">
                <ScoreBadge score={item.score} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────

export default function ExplorePage() {
  const [form, setForm] = useState<SearchForm>({
    market: "KRX",
    symbol: "",
    universe: DEFAULT_UNIVERSE,
    as_of: getTodayString(),
    top_k: DEFAULT_TOP_K,
  });

  const [results, setResults] = useState<SimilarItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** 폼 필드 부분 업데이트 핸들러 */
  function handleFormChange(updated: Partial<SearchForm>) {
    setForm((prev) => ({ ...prev, ...updated }));
  }

  /** 유사 종목 탐색 API 호출 */
  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setResults([]);

    try {
      const params = new URLSearchParams({
        market: form.market,
        universe: form.universe,
        as_of: form.as_of,
        top_k: String(form.top_k),
      });

      // next.config.ts rewrites 를 통해 백엔드(localhost:8000)로 프록시된다.
      const response = await fetch(`/api/similar/${encodeURIComponent(form.symbol)}?${params}`);

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`서버 오류 ${response.status}: ${body}`);
      }

      // WHY: 백엔드는 rank 가 없는 평평한 results 배열을 돌려주므로
      //      UI 측에서 내림차순 |score| 순서대로 rank 를 부여한다.
      const data: SimilarResponse = await response.json();
      const ranked: SimilarItem[] = data.results.map((item, index) => ({
        rank: index + 1,
        ticker: item.ticker,
        score: item.score,
      }));
      setResults(ranked);
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6">
      {/* ADR-000: 개인 전용 고지 문구 — 페이지 최상단 배치 필수 */}
      <DisclaimerBanner />

      {/* 헤더 */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--foreground)" }}>
          유사 종목 탐색기
        </h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Sim Money M1 — 유사도 공식: {SIMILARITY_FORMULA}
        </p>
      </div>

      {/* 탐색 폼 */}
      <section
        className="rounded-lg border p-6"
        style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
      >
        <ExploreForm
          form={form}
          isLoading={isLoading}
          onChange={handleFormChange}
          onSubmit={handleSubmit}
        />
      </section>

      {/* 에러 메시지 */}
      {error !== null && (
        <div
          className="rounded-md border px-4 py-3 text-sm"
          style={{
            borderColor: "var(--danger)",
            color: "var(--danger)",
            backgroundColor: "rgba(248,113,113,0.08)",
          }}
        >
          오류: {error}
        </div>
      )}

      {/* 로딩 인디케이터 */}
      {isLoading && (
        <div className="text-center text-sm py-4" style={{ color: "var(--muted)" }}>
          백엔드에서 유사도를 계산하는 중입니다...
        </div>
      )}

      {/* 결과 테이블 */}
      {results.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-base font-semibold" style={{ color: "var(--foreground)" }}>
            유사 종목 결과 — {form.symbol} 기준 상위 {results.length}개
          </h2>
          <ResultTable items={results} />
        </section>
      )}

      {/* 결과 없음 (제출 후 빈 배열) */}
      {!isLoading && results.length === 0 && error === null && form.symbol !== "" && (
        <p className="text-center text-sm py-4" style={{ color: "var(--muted)" }}>
          결과가 없습니다. 심볼 또는 유니버스를 확인하세요.
        </p>
      )}
    </main>
  );
}
