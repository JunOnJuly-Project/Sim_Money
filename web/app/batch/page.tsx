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
                {response.results.map((r, i) => (
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
