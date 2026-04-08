"use client";

// WHY: 사용자는 "양수 = 파랑이 진해지고 음수 = 빨강이 진해지는" 풀-셀 히트맵을
//      원한다. 이전 가변 폭 막대는 점수 크기를 보여주지만 진하기로 읽히진 않는다.
//      전체를 색으로 채우고 |score|/max 에 비례한 알파로 강도를 표현한다.

import { formatTickerLabel } from "./SymbolPicker";

interface Item {
  ticker: string;
  score: number;
}

interface SimilarityHeatmapProps {
  items: Item[];
  onRowClick?: (ticker: string) => void;
  selectedTicker?: string | null;
}

/** score 부호/강도 → 배경색. 양수=파랑 진해짐, 음수=빨강 진해짐. */
function scoreToColor(score: number, maxAbs: number): string {
  const intensity = Math.min(Math.abs(score) / (maxAbs || 1), 1);
  // 0.12 최저 알파로 가시성 유지, 1.0 까지 선형 증가
  const alpha = (0.12 + intensity * 0.88).toFixed(2);
  return score >= 0
    ? `rgba(37, 99, 235, ${alpha})` // blue-600
    : `rgba(220, 38, 38, ${alpha})`; // red-600
}

/** 셀이 진할 때는 흰 텍스트, 연할 때는 기본 텍스트. */
function textColorFor(score: number, maxAbs: number): string {
  const intensity = Math.min(Math.abs(score) / (maxAbs || 1), 1);
  return intensity > 0.5 ? "#ffffff" : "var(--foreground)";
}

export default function SimilarityHeatmap({
  items,
  onRowClick,
  selectedTicker,
}: SimilarityHeatmapProps) {
  if (items.length === 0) return null;

  const maxAbs = Math.max(...items.map((i) => Math.abs(i.score)), 0.0001);

  return (
    <div
      className="flex flex-col gap-2 rounded border p-3"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--card-bg)" }}
    >
      <div className="flex items-center justify-between text-xs" style={{ color: "var(--muted)" }}>
        <span>히트맵 — 파랑=양의 유사도, 빨강=음의 유사도 (진할수록 강함)</span>
        <span className="font-mono">max |score| = {maxAbs.toFixed(3)}</span>
      </div>

      {/* 색상 범례 */}
      <div className="flex items-center gap-2 text-[10px] font-mono" style={{ color: "var(--muted)" }}>
        <span>-{maxAbs.toFixed(2)}</span>
        <div
          className="h-2 flex-1 rounded"
          style={{
            background:
              "linear-gradient(to right, rgba(220,38,38,1), rgba(220,38,38,0.12), rgba(37,99,235,0.12), rgba(37,99,235,1))",
          }}
        />
        <span>+{maxAbs.toFixed(2)}</span>
      </div>

      <div className="flex flex-col gap-1">
        {items.map((it, idx) => {
          const parts = it.ticker.split(":");
          const market = parts.length >= 2 ? parts[0] : "";
          const sym = parts.length >= 2 ? parts.slice(1).join(":") : it.ticker;
          const label = formatTickerLabel(market || "KRX", sym);
          const isSelected = selectedTicker === it.ticker;
          const bg = scoreToColor(it.score, maxAbs);
          const fg = textColorFor(it.score, maxAbs);
          return (
            <button
              key={it.ticker}
              type="button"
              onClick={() => onRowClick?.(it.ticker)}
              className="group relative w-full rounded px-3 py-2 text-left text-xs transition-all hover:brightness-125"
              style={{
                backgroundColor: bg,
                border: isSelected ? "1.5px solid var(--accent)" : "1px solid rgba(255,255,255,0.06)",
                boxShadow: isSelected ? "0 0 0 2px rgba(56,189,248,0.25)" : "none",
              }}
            >
              <div className="flex items-center gap-3">
                <span className="w-6 font-mono text-right opacity-70" style={{ color: fg }}>
                  {idx + 1}
                </span>
                <span className="flex-1 truncate font-semibold" style={{ color: fg }}>
                  {label}
                </span>
                <span className="w-20 text-right font-mono tabular-nums" style={{ color: fg }}>
                  {it.score >= 0 ? "+" : ""}
                  {it.score.toFixed(4)}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
