"use client";

// WHY: 탐색 결과를 테이블만으로 보여주면 점수의 상대 크기/방향이 한눈에 들어오지
//      않는다. 히트맵(가로 막대 + 색 gradient) 로 양/음 스코어를 시각적으로 비교한다.
//      2D 매트릭스가 아니라 1xN 형태이므로 recharts 없이 순수 CSS 로 구현 가능하다.

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

/** score ∈ [-1, 1] 를 색상으로 매핑한다. 양수=청록, 음수=적색, 0 = 회색. */
function scoreToColor(score: number): string {
  // 절대값에 따라 알파 조절 (강도 표현), 부호에 따라 hue 분기.
  const alpha = Math.min(Math.abs(score), 1).toFixed(2);
  return score >= 0
    ? `rgba(56, 189, 248, ${alpha})` // cyan-400
    : `rgba(248, 113, 113, ${alpha})`; // red-400
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
      className="flex flex-col gap-1 rounded border p-3"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--card-bg)" }}
    >
      <div className="mb-1 flex justify-between text-xs" style={{ color: "var(--muted)" }}>
        <span>히트맵 (점수 크기/방향)</span>
        <span className="font-mono">max |score| = {maxAbs.toFixed(3)}</span>
      </div>

      {items.map((it, idx) => {
        const parts = it.ticker.split(":");
        const market = parts.length >= 2 ? parts[0] : "";
        const sym = parts.length >= 2 ? parts.slice(1).join(":") : it.ticker;
        const label = formatTickerLabel(market || "KRX", sym);
        const widthPct = Math.min(100, (Math.abs(it.score) / maxAbs) * 100);
        const isSelected = selectedTicker === it.ticker;
        return (
          <button
            key={it.ticker}
            type="button"
            onClick={() => onRowClick?.(it.ticker)}
            className="group relative w-full rounded px-2 py-1 text-left text-xs transition-colors"
            style={{
              backgroundColor: isSelected ? "rgba(56,189,248,0.08)" : "transparent",
              border: isSelected ? "1px solid var(--accent)" : "1px solid transparent",
            }}
          >
            <div className="relative flex items-center gap-2">
              {/* 순위 */}
              <span className="w-6 font-mono text-right" style={{ color: "var(--muted)" }}>
                {idx + 1}
              </span>
              {/* 티커 라벨 */}
              <span className="w-44 truncate font-medium" style={{ color: "var(--foreground)" }}>
                {label}
              </span>
              {/* 히트맵 바 — flex-1 컨테이너 */}
              <div
                className="relative h-4 flex-1 rounded"
                style={{ backgroundColor: "rgba(255,255,255,0.04)" }}
              >
                <div
                  className="absolute left-0 top-0 h-full rounded transition-all"
                  style={{
                    width: `${widthPct}%`,
                    backgroundColor: scoreToColor(it.score),
                  }}
                />
              </div>
              {/* 스코어 수치 */}
              <span className="w-16 text-right font-mono" style={{ color: "var(--accent)" }}>
                {it.score.toFixed(4)}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
