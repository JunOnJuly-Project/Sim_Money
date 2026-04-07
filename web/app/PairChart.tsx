"use client";

// WHY: recharts 는 DOM 이벤트를 직접 사용하므로 SSR 환경에서는 동작하지 않는다.
//      "use client" 지시어로 클라이언트 번들에만 포함되도록 강제한다.
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  ReferenceLine,
} from "recharts";
import { useEffect, useState } from "react";

// ── 타입 정의 ──────────────────────────────────────────────────────────────

/** /api/pair/{a}/{b} 엔드포인트 응답 스키마 */
interface PairResponse {
  a: string;
  b: string;
  dates: string[];
  log_returns_a: number[];
  log_returns_b: number[];
  rolling_corr: {
    window: number;
    values: (number | null)[];
  };
}

/** 산점도 한 점: x=A 로그수익률, y=B 로그수익률 */
interface ScatterPoint {
  x: number;
  y: number;
}

/** 롤링 상관 라인차트 한 점: date + 상관계수 값 */
interface CorrPoint {
  date: string;
  corr: number | null;
}

// ── PairChart props ─────────────────────────────────────────────────────────

export interface PairChartProps {
  /** target 마켓 코드 (예: KRX) */
  market: string;
  /** target 심볼 (예: 005930) */
  symbolA: string;
  /** peer 마켓 코드 (예: KRX) */
  marketB: string;
  /** peer 심볼 (예: 000660) */
  symbolB: string;
  /** 기준일 YYYY-MM-DD */
  asOf: string;
}

// ── 상수 ───────────────────────────────────────────────────────────────────

const CHART_HEIGHT = 260;
const SCATTER_DOT_RADIUS = 2;
// WHY: 산점도 점이 너무 많으면 렌더 비용이 크다. opacity 를 낮춰 겹침을 시각적으로 표현한다.
const SCATTER_DOT_OPACITY = 0.5;

// ── 헬퍼 함수 ──────────────────────────────────────────────────────────────

/**
 * PairResponse 를 산점도용 배열로 변환한다.
 * WHY: recharts ScatterChart 는 { x, y } 형태의 배열을 요구하므로
 *      인덱스 기준으로 두 수익률 배열을 zip 한다.
 */
function buildScatterPoints(data: PairResponse): ScatterPoint[] {
  return data.log_returns_a.map((x, i) => ({
    x,
    y: data.log_returns_b[i],
  }));
}

/**
 * PairResponse 를 롤링 상관 라인차트용 배열로 변환한다.
 * WHY: null 값은 recharts 가 자동으로 선 끊김(gap)으로 처리하므로 그대로 유지한다.
 */
function buildCorrPoints(data: PairResponse): CorrPoint[] {
  return data.dates.map((date, i) => ({
    date,
    corr: data.rolling_corr.values[i],
  }));
}

/**
 * API URL을 조립한다.
 * WHY: 심볼에 특수문자가 포함될 수 있어 encodeURIComponent 를 명시적으로 적용한다.
 */
function buildApiUrl(props: PairChartProps): string {
  const { market, symbolA, marketB, symbolB, asOf } = props;
  const a = encodeURIComponent(`${market}:${symbolA}`);
  const b = encodeURIComponent(`${marketB}:${symbolB}`);
  const params = new URLSearchParams({
    market_a: market,
    market_b: marketB,
    as_of: asOf,
  });
  return `/api/pair/${a}/${b}?${params}`;
}

// ── 서브 컴포넌트: 로딩 인디케이터 ───────────────────────────────────────

function ChartLoading() {
  return (
    <div className="text-center py-8 text-sm" style={{ color: "var(--muted)" }}>
      차트 데이터를 불러오는 중입니다...
    </div>
  );
}

// ── 서브 컴포넌트: 에러 표시 ───────────────────────────────────────────────

function ChartError({ message }: { message: string }) {
  return (
    <div
      className="rounded-md border px-4 py-3 text-sm"
      style={{
        borderColor: "var(--danger)",
        color: "var(--danger)",
        backgroundColor: "rgba(248,113,113,0.08)",
      }}
    >
      차트 로드 오류: {message}
    </div>
  );
}

// ── 서브 컴포넌트: 산점도 ─────────────────────────────────────────────────

function ReturnScatterChart({
  points,
  labelA,
  labelB,
}: {
  points: ScatterPoint[];
  labelA: string;
  labelB: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-medium" style={{ color: "var(--muted)" }}>
        로그수익률 산점도 — {labelA} vs {labelB}
      </p>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
          <XAxis
            dataKey="x"
            type="number"
            name={labelA}
            tick={{ fontSize: 10, fill: "var(--muted)" }}
            label={{ value: labelA, position: "insideBottom", offset: -4, fontSize: 11, fill: "var(--muted)" }}
          />
          <YAxis
            dataKey="y"
            type="number"
            name={labelB}
            tick={{ fontSize: 10, fill: "var(--muted)" }}
            label={{ value: labelB, angle: -90, position: "insideLeft", fontSize: 11, fill: "var(--muted)" }}
          />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            contentStyle={{
              backgroundColor: "var(--card-bg)",
              border: "1px solid var(--border)",
              fontSize: 11,
            }}
            formatter={(value: number) => value.toFixed(5)}
          />
          {/* WHY: fillOpacity 로 점이 겹치는 영역의 밀도를 시각적으로 파악할 수 있다. */}
          <Scatter
            data={points}
            fill="var(--accent)"
            fillOpacity={SCATTER_DOT_OPACITY}
            r={SCATTER_DOT_RADIUS}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── 서브 컴포넌트: 롤링 상관 라인차트 ────────────────────────────────────

function RollingCorrLineChart({
  points,
  window,
}: {
  points: CorrPoint[];
  window: number;
}) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-medium" style={{ color: "var(--muted)" }}>
        롤링 상관계수 (window={window}일)
      </p>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 9, fill: "var(--muted)" }}
            // WHY: 날짜가 많으면 라벨이 겹치므로 일정 간격만 표시한다.
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[-1, 1]}
            tick={{ fontSize: 10, fill: "var(--muted)" }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--card-bg)",
              border: "1px solid var(--border)",
              fontSize: 11,
            }}
            formatter={(value: number | null) =>
              value !== null ? value.toFixed(4) : "-"
            }
          />
          {/* WHY: 0 기준선을 표시하면 양/음 상관 구간을 빠르게 식별할 수 있다. */}
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.2)" strokeDasharray="4 2" />
          <Line
            type="monotone"
            dataKey="corr"
            stroke="var(--accent)"
            dot={false}
            // WHY: connectNulls=false 로 두면 null 구간(초기 window 미달)에서 선이 끊겨
            //      데이터 부재를 정직하게 표현한다.
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────

/**
 * target-peer 쌍의 산점도와 롤링 상관계수 차트를 렌더한다.
 * mount 시 /api/pair 엔드포인트에서 데이터를 fetch 한다.
 */
export default function PairChart(props: PairChartProps) {
  const { market, symbolA, marketB, symbolB, asOf } = props;

  const [data, setData] = useState<PairResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // WHY: props 가 바뀔 때마다 새 데이터를 fetch 해야 하므로 의존성 배열에 모두 포함한다.
    let cancelled = false;

    async function fetchPairData() {
      setIsLoading(true);
      setError(null);
      setData(null);

      try {
        const url = buildApiUrl(props);
        const response = await fetch(url);

        if (!response.ok) {
          const body = await response.text();
          throw new Error(`서버 오류 ${response.status}: ${body}`);
        }

        const json: PairResponse = await response.json();
        if (!cancelled) setData(json);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "알 수 없는 오류");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    fetchPairData();

    // WHY: 컴포넌트가 언마운트되거나 props 가 바뀌면 이전 fetch 결과를 무시해
    //      stale 상태 업데이트를 방지한다.
    return () => {
      cancelled = true;
    };
  }, [market, symbolA, marketB, symbolB, asOf]);

  const labelA = `${market}:${symbolA}`;
  const labelB = `${marketB}:${symbolB}`;

  return (
    <div
      className="rounded-lg border p-5 flex flex-col gap-6"
      style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
    >
      {/* 섹션 헤더 */}
      <div className="flex flex-col gap-0.5">
        <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
          쌍 시각화 — {labelA} vs {labelB}
        </h3>
        <p className="text-xs" style={{ color: "var(--muted)" }}>
          기준일: {asOf}
        </p>
      </div>

      {isLoading && <ChartLoading />}
      {error !== null && <ChartError message={error} />}

      {data !== null && (
        <>
          <ReturnScatterChart
            points={buildScatterPoints(data)}
            labelA={labelA}
            labelB={labelB}
          />
          <RollingCorrLineChart
            points={buildCorrPoints(data)}
            window={data.rolling_corr.window}
          />
        </>
      )}
    </div>
  );
}
