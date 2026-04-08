"use client";

// WHY: 1D 히트맵은 유사도 한 축만 보여 "가짜 페어"(둘 다 저변동이라 닮아 보임)
//      를 구별하지 못한다. 2D 스캐터로 x=연환산 변동성, y=유사도 를 동시에
//      시각화해 페어 트레이딩 후보(고유사·충분한 변동성)를 직관적으로 찾는다.

import { formatTickerLabel } from "./SymbolPicker";

interface Item {
  ticker: string;
  score: number;
  volatility: number | null;
}

interface SimilarityScatterProps {
  items: Item[];
  targetTicker?: string;
  targetVolatility?: number | null;
  onPointClick?: (ticker: string) => void;
  selectedTicker?: string | null;
}

// WHY: SVG viewBox 상수. 고정 좌표계로 반응형 스케일링은 CSS width=100% 로 해결.
const VB_W = 600;
const VB_H = 360;
const MARGIN = { top: 20, right: 20, bottom: 40, left: 50 };
const PLOT_W = VB_W - MARGIN.left - MARGIN.right;
const PLOT_H = VB_H - MARGIN.top - MARGIN.bottom;

function scoreColor(score: number, maxAbs: number): string {
  const intensity = Math.min(Math.abs(score) / (maxAbs || 1), 1);
  const alpha = (0.25 + intensity * 0.75).toFixed(2);
  return score >= 0
    ? `rgba(37, 99, 235, ${alpha})`
    : `rgba(220, 38, 38, ${alpha})`;
}

export default function SimilarityScatter({
  items,
  targetTicker,
  targetVolatility,
  onPointClick,
  selectedTicker,
}: SimilarityScatterProps) {
  // 변동성 결측 데이터는 스캐터에서 제외 (결측 리스트로 별도 안내)
  const plotItems = items.filter((it) => it.volatility !== null);
  const missingItems = items.filter((it) => it.volatility === null);

  if (plotItems.length === 0) {
    return (
      <p className="text-xs" style={{ color: "var(--muted)" }}>
        변동성 데이터가 부족해 스캐터를 그릴 수 없습니다.
      </p>
    );
  }

  // 축 범위
  const vols = plotItems.map((i) => i.volatility as number);
  if (typeof targetVolatility === "number") vols.push(targetVolatility);
  const volMin = Math.min(...vols) * 0.9;
  const volMax = Math.max(...vols) * 1.1;
  const scores = plotItems.map((i) => i.score);
  const scoreMin = Math.min(...scores, 0);
  const scoreMax = Math.max(...scores, 0);
  const scorePad = (scoreMax - scoreMin) * 0.1 || 0.1;
  const yMin = scoreMin - scorePad;
  const yMax = scoreMax + scorePad;
  const maxAbsScore = Math.max(Math.abs(scoreMin), Math.abs(scoreMax), 0.0001);

  const xScale = (v: number) => ((v - volMin) / (volMax - volMin)) * PLOT_W;
  const yScale = (s: number) => PLOT_H - ((s - yMin) / (yMax - yMin)) * PLOT_H;

  // 격자 눈금 — 5 분할
  const xTicks = Array.from({ length: 5 }, (_, i) => volMin + ((volMax - volMin) * i) / 4);
  const yTicks = Array.from({ length: 5 }, (_, i) => yMin + ((yMax - yMin) * i) / 4);

  return (
    <div
      className="flex flex-col gap-2 rounded border p-3"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--card-bg)" }}
    >
      <div className="flex items-center justify-between text-xs" style={{ color: "var(--muted)" }}>
        <span>2D 스캐터 — x: 연환산 변동성(σ), y: 유사도 스코어</span>
        <span className="font-mono">N = {plotItems.length}</span>
      </div>

      <svg
        viewBox={`0 0 ${VB_W} ${VB_H}`}
        className="w-full"
        style={{ maxHeight: 420 }}
      >
        <g transform={`translate(${MARGIN.left}, ${MARGIN.top})`}>
          {/* 격자 */}
          {xTicks.map((t, i) => (
            <line
              key={`gx${i}`}
              x1={xScale(t)}
              x2={xScale(t)}
              y1={0}
              y2={PLOT_H}
              stroke="rgba(255,255,255,0.05)"
            />
          ))}
          {yTicks.map((t, i) => (
            <line
              key={`gy${i}`}
              x1={0}
              x2={PLOT_W}
              y1={yScale(t)}
              y2={yScale(t)}
              stroke="rgba(255,255,255,0.05)"
            />
          ))}

          {/* y=0 기준선 */}
          {yMin <= 0 && yMax >= 0 && (
            <line
              x1={0}
              x2={PLOT_W}
              y1={yScale(0)}
              y2={yScale(0)}
              stroke="rgba(255,255,255,0.2)"
              strokeDasharray="3 3"
            />
          )}

          {/* 쿼리 타겟 기준 세로선 */}
          {typeof targetVolatility === "number" && (
            <line
              x1={xScale(targetVolatility)}
              x2={xScale(targetVolatility)}
              y1={0}
              y2={PLOT_H}
              stroke="rgba(56,189,248,0.3)"
              strokeDasharray="4 4"
            />
          )}

          {/* 데이터 포인트 */}
          {plotItems.map((it) => {
            const cx = xScale(it.volatility as number);
            const cy = yScale(it.score);
            const isSelected = selectedTicker === it.ticker;
            return (
              <g key={it.ticker} style={{ cursor: "pointer" }}>
                <circle
                  cx={cx}
                  cy={cy}
                  r={isSelected ? 9 : 6}
                  fill={scoreColor(it.score, maxAbsScore)}
                  stroke={isSelected ? "#38bdf8" : "rgba(255,255,255,0.4)"}
                  strokeWidth={isSelected ? 2 : 1}
                  onClick={() => onPointClick?.(it.ticker)}
                >
                  <title>{`${it.ticker}\nscore=${it.score.toFixed(4)}\nσ=${(it.volatility as number).toFixed(3)}`}</title>
                </circle>
                {isSelected && (
                  <text
                    x={cx + 12}
                    y={cy + 4}
                    fontSize="11"
                    fill="#e2e8f0"
                    style={{ pointerEvents: "none" }}
                  >
                    {formatTickerLabel(
                      it.ticker.split(":")[0] || "",
                      it.ticker.split(":").slice(1).join(":") || it.ticker
                    )}
                  </text>
                )}
              </g>
            );
          })}

          {/* 쿼리 타겟 표식 (다이아몬드) */}
          {typeof targetVolatility === "number" && targetTicker && (
            <g>
              <rect
                x={xScale(targetVolatility) - 6}
                y={yScale(yMax) - 6}
                width={12}
                height={12}
                fill="rgba(56,189,248,0.2)"
                stroke="#38bdf8"
                strokeWidth={1.5}
                transform={`rotate(45, ${xScale(targetVolatility)}, ${yScale(yMax)})`}
              />
              <text
                x={xScale(targetVolatility) + 10}
                y={yScale(yMax) + 4}
                fontSize="10"
                fill="#38bdf8"
              >
                기준: {targetTicker.split(":").slice(1).join(":")}
              </text>
            </g>
          )}

          {/* X 축 */}
          <line x1={0} x2={PLOT_W} y1={PLOT_H} y2={PLOT_H} stroke="rgba(255,255,255,0.3)" />
          {xTicks.map((t, i) => (
            <text
              key={`xt${i}`}
              x={xScale(t)}
              y={PLOT_H + 16}
              fontSize="10"
              fill="#94a3b8"
              textAnchor="middle"
            >
              {t.toFixed(2)}
            </text>
          ))}
          <text
            x={PLOT_W / 2}
            y={PLOT_H + 32}
            fontSize="11"
            fill="#94a3b8"
            textAnchor="middle"
          >
            연환산 변동성 (σ)
          </text>

          {/* Y 축 */}
          <line x1={0} x2={0} y1={0} y2={PLOT_H} stroke="rgba(255,255,255,0.3)" />
          {yTicks.map((t, i) => (
            <text
              key={`yt${i}`}
              x={-6}
              y={yScale(t) + 3}
              fontSize="10"
              fill="#94a3b8"
              textAnchor="end"
            >
              {t.toFixed(2)}
            </text>
          ))}
          <text
            x={-PLOT_H / 2}
            y={-36}
            fontSize="11"
            fill="#94a3b8"
            textAnchor="middle"
            transform="rotate(-90)"
          >
            유사도 스코어
          </text>
        </g>
      </svg>

      <p className="text-[10px]" style={{ color: "var(--muted)" }}>
        우상단(높은 유사도 + 충분한 변동성) = 페어 트레이딩 유력 후보.
        저변동 영역은 z-score 가 임계값에 잘 도달하지 않아 실거래 가치가 낮습니다.
      </p>
      {missingItems.length > 0 && (
        <p className="text-[10px]" style={{ color: "var(--muted)" }}>
          변동성 계산 불가(데이터 부족): {missingItems.map((i) => i.ticker).join(", ")}
        </p>
      )}
    </div>
  );
}
