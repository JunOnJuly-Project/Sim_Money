"use client";

// WHY: 여러 페어를 한 번에 백테스트해 결과를 비교하기 위한 최소 UI.
//      백엔드 POST /backtest/batch 를 호출한다.

import { useState, FormEvent } from "react";
import Link from "next/link";

interface PairInput {
  id: number;
  a: string;
  b: string;
}

interface PairMetrics {
  total_return: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  max_drawdown: number;
  win_rate: number | null;
}

interface PairResult {
  pair: { a: string; b: string };
  metrics?: PairMetrics;
  trade_count?: number;
  error?: string;
}

interface BatchResponse {
  aggregate: {
    pair_count: number;
    success_count: number;
    avg_total_return?: number;
    avg_sharpe?: number;
  };
  results: PairResult[];
}

let _nextId = 1;
const genId = () => _nextId++;

export default function BatchPage() {
  const [pairs, setPairs] = useState<PairInput[]>([
    { id: genId(), a: "", b: "" },
  ]);
  const [response, setResponse] = useState<BatchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState<"none" | "total_return" | "sharpe" | "sortino" | "max_drawdown">("none");
  const [hideErrors, setHideErrors] = useState(false);

  // WHY: 실패 행은 항상 뒤로 밀어 순위 왜곡을 방지한다.
  function sortedResults(results: PairResult[]): PairResult[] {
    const ok = results.filter((r) => r.metrics !== undefined);
    const bad = results.filter((r) => r.metrics === undefined);
    if (sortKey !== "none") {
      ok.sort((a, b) => {
        const av = a.metrics![sortKey];
        const bv = b.metrics![sortKey];
        // max_drawdown 은 음수라 오름차순(덜 나쁜 순), 나머지는 내림차순.
        return sortKey === "max_drawdown" ? av - bv : bv - av;
      });
    }
    return hideErrors ? ok : [...ok, ...bad];
  }

  function downloadCsv() {
    if (response === null) return;
    const header = ["pair_a", "pair_b", "total_return", "sharpe", "sortino", "calmar", "max_drawdown", "win_rate", "trade_count", "error"];
    const rows: (string | number)[][] = [header];
    for (const r of sortedResults(response.results)) {
      rows.push([
        r.pair.a,
        r.pair.b,
        r.metrics?.total_return ?? "",
        r.metrics?.sharpe ?? "",
        r.metrics?.sortino ?? "",
        r.metrics?.calmar ?? "",
        r.metrics?.max_drawdown ?? "",
        r.metrics?.win_rate ?? "",
        r.trade_count ?? "",
        r.error ?? "",
      ]);
    }
    const csv = rows.map((row) => row.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `batch-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function addPair() {
    setPairs((prev) => [...prev, { id: genId(), a: "", b: "" }]);
  }
  function removePair(id: number) {
    setPairs((prev) => prev.filter((p) => p.id !== id));
  }
  function updatePair(id: number, field: "a" | "b", value: string) {
    setPairs((prev) => prev.map((p) => (p.id === id ? { ...p, [field]: value } : p)));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const body = {
        pairs: pairs.map((p) => ({ a: p.a, b: p.b })),
      };
      const res = await fetch("/api/backtest/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`서버 오류 ${res.status}: ${text}`);
      }
      setResponse((await res.json()) as BatchResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6">
      <div
        className="w-full rounded-md border px-4 py-2 text-sm text-center"
        style={{ borderColor: "var(--muted)", color: "var(--muted)", backgroundColor: "var(--card-bg)" }}
      >
        본 도구는 개인 전용 실험이며 투자 조언이 아닙니다.
      </div>

      <div className="flex gap-3">
        <Link
          href="/"
          className="rounded-md border px-3 py-1.5 text-sm"
          style={{ borderColor: "var(--border)", color: "var(--muted)", backgroundColor: "var(--card-bg)" }}
        >
          홈으로
        </Link>
        <Link
          href="/backtest"
          className="rounded-md border px-3 py-1.5 text-sm"
          style={{ borderColor: "var(--accent)", color: "var(--accent)", backgroundColor: "rgba(56,189,248,0.08)" }}
        >
          단일 백테스트
        </Link>
      </div>

      <h1 className="text-2xl font-bold" style={{ color: "var(--foreground)" }}>
        배치 백테스트
      </h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <section
          className="rounded-lg border p-6 flex flex-col gap-3"
          style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
              페어 목록
            </span>
            <button
              type="button"
              onClick={addPair}
              className="rounded px-3 py-1 text-xs border"
              style={{ borderColor: "var(--accent)", color: "var(--accent)", backgroundColor: "rgba(56,189,248,0.08)" }}
            >
              페어 추가
            </button>
          </div>
          {pairs.map((p) => (
            <div key={p.id} className="flex items-center gap-2">
              <input
                type="text"
                placeholder="A (예: AAA)"
                value={p.a}
                onChange={(e) => updatePair(p.id, "a", e.target.value)}
                className="flex-1 rounded border px-2 py-1 text-sm"
                style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)", color: "var(--foreground)" }}
              />
              <span style={{ color: "var(--muted)" }}>vs</span>
              <input
                type="text"
                placeholder="B (예: BBB)"
                value={p.b}
                onChange={(e) => updatePair(p.id, "b", e.target.value)}
                className="flex-1 rounded border px-2 py-1 text-sm"
                style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)", color: "var(--foreground)" }}
              />
              <button
                type="button"
                onClick={() => removePair(p.id)}
                className="text-xs"
                style={{ color: "var(--danger)" }}
              >
                삭제
              </button>
            </div>
          ))}
        </section>
        <button
          type="submit"
          disabled={loading}
          className="rounded-md px-4 py-2 text-sm font-semibold disabled:opacity-50"
          style={{ backgroundColor: "var(--accent)", color: "#0f172a" }}
        >
          {loading ? "실행 중..." : "배치 실행"}
        </button>
      </form>

      {error !== null && (
        <div
          className="rounded-md border px-4 py-3 text-sm"
          style={{ borderColor: "var(--danger)", color: "var(--danger)", backgroundColor: "rgba(248,113,113,0.08)" }}
        >
          오류: {error}
        </div>
      )}

      {response !== null && (
        <section className="flex flex-col gap-3">
          <div
            className="rounded-md border px-4 py-3 text-xs font-mono"
            style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)", color: "var(--muted)" }}
          >
            총 {response.aggregate.pair_count} / 성공 {response.aggregate.success_count}
            {response.aggregate.avg_total_return !== undefined && (
              <>
                {" "}· 평균 수익률 {(response.aggregate.avg_total_return * 100).toFixed(2)}% · 평균 Sharpe{" "}
                {response.aggregate.avg_sharpe?.toFixed(4)}
              </>
            )}
          </div>
          <div className="flex items-center gap-3 flex-wrap text-xs">
            <label className="flex items-center gap-1" style={{ color: "var(--muted)" }}>
              정렬
              <select
                value={sortKey}
                onChange={(e) => setSortKey(e.target.value as typeof sortKey)}
                className="rounded border px-2 py-1"
                style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)", color: "var(--foreground)" }}
              >
                <option value="none">원래 순서</option>
                <option value="total_return">수익률 ↓</option>
                <option value="sharpe">Sharpe ↓</option>
                <option value="sortino">Sortino ↓</option>
                <option value="max_drawdown">MDD ↑(덜 나쁨)</option>
              </select>
            </label>
            <label className="flex items-center gap-1" style={{ color: "var(--muted)" }}>
              <input type="checkbox" checked={hideErrors} onChange={(e) => setHideErrors(e.target.checked)} />
              실패 숨김
            </label>
            <button
              type="button"
              onClick={downloadCsv}
              className="rounded border px-3 py-1"
              style={{ borderColor: "var(--accent)", color: "var(--accent)", backgroundColor: "rgba(56,189,248,0.08)" }}
            >
              CSV 내보내기
            </button>
          </div>
          <div className="overflow-x-auto rounded-md border" style={{ borderColor: "var(--border)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: "var(--card-bg)", borderBottom: "1px solid var(--border)" }}>
                  <th className="px-3 py-2 text-left" style={{ color: "var(--muted)" }}>Pair</th>
                  <th className="px-3 py-2 text-right" style={{ color: "var(--muted)" }}>수익률</th>
                  <th className="px-3 py-2 text-right" style={{ color: "var(--muted)" }}>Sharpe</th>
                  <th className="px-3 py-2 text-right" style={{ color: "var(--muted)" }}>Sortino</th>
                  <th className="px-3 py-2 text-right" style={{ color: "var(--muted)" }}>MDD</th>
                  <th className="px-3 py-2 text-right" style={{ color: "var(--muted)" }}>거래</th>
                </tr>
              </thead>
              <tbody>
                {sortedResults(response.results).map((r, i) => (
                  <tr key={i} className="border-t" style={{ borderColor: "var(--border)" }}>
                    <td className="px-3 py-2 font-mono" style={{ color: "var(--foreground)" }}>
                      {r.pair.a} / {r.pair.b}
                    </td>
                    {r.error !== undefined ? (
                      <td colSpan={5} className="px-3 py-2 text-xs" style={{ color: "var(--danger)" }}>
                        {r.error}
                      </td>
                    ) : (
                      <>
                        <td className="px-3 py-2 text-right font-mono">
                          {(r.metrics!.total_return * 100).toFixed(2)}%
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {r.metrics!.sharpe.toFixed(3)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {r.metrics!.sortino.toFixed(3)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {(r.metrics!.max_drawdown * 100).toFixed(2)}%
                        </td>
                        <td className="px-3 py-2 text-right font-mono">{r.trade_count}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
