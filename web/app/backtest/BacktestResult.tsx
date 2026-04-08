"use client";

// WHY: recharts 는 DOM 이벤트에 의존하므로 서버 렌더링 불가.
//      "use client" 지시어로 클라이언트 번들에만 포함시킨다.
import { useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

// ── 타입 정의 ──────────────────────────────────────────────────────────────

/** /api/backtest/pair/{a}/{b} 응답의 metrics 필드 */
interface BacktestMetrics {
  total_return: number;
  sharpe: number | null;
  max_drawdown: number;
  win_rate: number | null;
  sortino: number;
  calmar: number;
}

/** 단일 체결 거래 */
interface Trade {
  ticker: string;
  entry_time: string;
  exit_time: string;
  pnl: number;
}

/** equity_curve 한 점 */
interface EquityPoint {
  timestamp: string;
  value: number;
}

/** signals_count 필드 */
interface SignalsCount {
  long: number;
  short: number;
  exit: number;
}

/** /api/backtest/pair 전체 응답 스키마 */
export interface BacktestResponse {
  pair: { a: string; b: string };
  metrics: BacktestMetrics;
  trades: Trade[];
  equity_curve: EquityPoint[];
  signals_count: SignalsCount;
  config: BacktestConfigEcho;
}

/** 요청 시 사용된 백테스트 설정 에코 */
export interface BacktestConfigEcho {
  lookback: number;
  entry: number;
  exit: number;
  initial: number;
  fee: number;
  slippage: number;
  rfr: number;
  sizer: string;
  max_position_weight: number;
  cash_buffer: number;
}

// ── 상수 ──────────────────────────────────────────────────────────────────

const CHART_HEIGHT = 260;
const DECIMAL_PLACES = 4;

// ── 서브 컴포넌트: Metrics 카드 그룹 ─────────────────────────────────────

interface MetricCardProps {
  label: string;
  value: string;
  /** 양수이면 초록, 음수이면 빨간색으로 표시한다 */
  isPositive?: boolean;
}

/** 단일 지표 카드 */
function MetricCard({ label, value, isPositive }: MetricCardProps) {
  const valueColor =
    isPositive === undefined
      ? "var(--foreground)"
      : isPositive
      ? "var(--success)"
      : "var(--danger)";

  return (
    <div
      className="flex flex-col gap-1 rounded-md border px-4 py-3"
      style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
    >
      <span className="text-xs font-medium" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <span className="text-lg font-bold font-mono" style={{ color: valueColor }}>
        {value}
      </span>
    </div>
  );
}

/** 백테스트 핵심 지표 4개를 카드 그리드로 렌더한다 */
function MetricsSection({ metrics }: { metrics: BacktestMetrics }) {
  const totalReturnPct = (metrics.total_return * 100).toFixed(2);
  const isReturnPositive = metrics.total_return >= 0;

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
        성과 지표
      </h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard
          label="총 수익률"
          value={`${isReturnPositive ? "+" : ""}${totalReturnPct}%`}
          isPositive={isReturnPositive}
        />
        <MetricCard
          label="샤프 비율"
          value={metrics.sharpe !== null ? metrics.sharpe.toFixed(DECIMAL_PLACES) : "-"}
        />
        <MetricCard
          label="Sortino"
          value={metrics.sortino.toFixed(DECIMAL_PLACES)}
          isPositive={metrics.sortino >= 0}
        />
        <MetricCard
          label="Calmar"
          value={metrics.calmar.toFixed(DECIMAL_PLACES)}
          isPositive={metrics.calmar >= 0}
        />
        <MetricCard
          label="최대 낙폭"
          value={`${(metrics.max_drawdown * 100).toFixed(2)}%`}
          isPositive={metrics.max_drawdown <= 0}
        />
        <MetricCard
          label="승률"
          value={metrics.win_rate !== null ? `${(metrics.win_rate * 100).toFixed(1)}%` : "-"}
        />
      </div>
    </div>
  );
}

// ── 서브 컴포넌트: 자본 곡선 차트 ────────────────────────────────────────

/** equity_curve 배열을 recharts LineChart 로 렌더한다 */
function EquityCurveChart({ equityCurve }: { equityCurve: EquityPoint[] }) {
  if (equityCurve.length === 0) {
    return (
      <p className="text-sm text-center py-4" style={{ color: "var(--muted)" }}>
        자본 곡선 데이터 없음
      </p>
    );
  }

  // WHY: ISO 타임스탬프를 날짜 문자열로 축약해 x축 가독성을 높인다
  const chartData = equityCurve.map((p) => ({
    date: p.timestamp.slice(0, 10),
    value: p.value,
  }));

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
        자본 곡선
      </h3>
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 9, fill: "var(--muted)" }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10, fill: "var(--muted)" }}
            tickFormatter={(v: number) => v.toLocaleString("ko-KR")}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--card-bg)",
              border: "1px solid var(--border)",
              fontSize: 11,
            }}
            formatter={(value: number) => [
              value.toLocaleString("ko-KR", { minimumFractionDigits: 2 }),
              "자본",
            ]}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--accent)"
            dot={false}
            strokeWidth={1.5}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── 서브 컴포넌트: 거래 내역 테이블 ─────────────────────────────────────

// WHY: 거래 내역은 양이 많을 때 카테고리·정렬로 탐색해야 인사이트가 나온다.
//      ⚠ 현재 백테스트 엔진(InMemoryTradeExecutor) 은 LONG 진입만 지원하므로
//      모든 Trade 는 LONG→청산 라운드트립. SHORT 신호는 signals_count 에만 집계되며
//      실제 체결되지 않는다. 필터는 "결과(수익/손실)" + "티커" 축으로 구성한다.

type TradeFilter = "all" | "profit" | "loss";
type TradeSortKey = "entry" | "exit" | "pnl" | "duration";
type SortOrder = "asc" | "desc";

function holdingDays(t: Trade): number {
  const e = new Date(t.entry_time).getTime();
  const x = new Date(t.exit_time).getTime();
  return (x - e) / (1000 * 60 * 60 * 24);
}

function TradesTable({ trades }: { trades: Trade[] }) {
  const [filter, setFilter] = useState<TradeFilter>("all");
  const [tickerFilter, setTickerFilter] = useState<string>("ALL");
  const [sortKey, setSortKey] = useState<TradeSortKey>("entry");
  const [order, setOrder] = useState<SortOrder>("desc");

  // 티커 목록 (중복 제거)
  const tickers = useMemo(() => {
    const set = new Set(trades.map((t) => t.ticker));
    return ["ALL", ...Array.from(set).sort()];
  }, [trades]);

  const filtered = useMemo(() => {
    let arr = trades;
    if (filter === "profit") arr = arr.filter((t) => t.pnl >= 0);
    else if (filter === "loss") arr = arr.filter((t) => t.pnl < 0);
    if (tickerFilter !== "ALL") arr = arr.filter((t) => t.ticker === tickerFilter);

    const sorted = [...arr].sort((a, b) => {
      let d = 0;
      if (sortKey === "entry") d = new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime();
      else if (sortKey === "exit") d = new Date(a.exit_time).getTime() - new Date(b.exit_time).getTime();
      else if (sortKey === "pnl") d = a.pnl - b.pnl;
      else if (sortKey === "duration") d = holdingDays(a) - holdingDays(b);
      return order === "asc" ? d : -d;
    });
    return sorted;
  }, [trades, filter, tickerFilter, sortKey, order]);

  const profitCount = trades.filter((t) => t.pnl >= 0).length;
  const lossCount = trades.length - profitCount;

  if (trades.length === 0) {
    return (
      <p className="text-sm text-center py-4" style={{ color: "var(--muted)" }}>
        체결 거래 없음
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
          거래 내역 ({filtered.length}/{trades.length}건)
        </h3>
        <p className="text-[11px]" style={{ color: "var(--muted)" }}>
          ⚠ 현재 엔진은 LONG 진입만 체결합니다. SHORT 신호는 생성되나 실거래로 변환되지 않습니다.
        </p>
      </div>

      {/* 필터 바 */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {/* 결과 필터 */}
        <div className="flex gap-1 rounded-md border p-0.5" style={{ borderColor: "var(--border)" }}>
          {(
            [
              ["all", `전체 ${trades.length}`],
              ["profit", `수익 ${profitCount}`],
              ["loss", `손실 ${lossCount}`],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => setFilter(k)}
              className="rounded px-2.5 py-1 transition-colors"
              style={{
                backgroundColor: filter === k ? "rgba(56,189,248,0.18)" : "transparent",
                color: filter === k ? "var(--accent)" : "var(--muted)",
                fontWeight: filter === k ? 600 : 400,
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 티커 필터 */}
        {tickers.length > 2 && (
          <select
            value={tickerFilter}
            onChange={(e) => setTickerFilter(e.target.value)}
            className="rounded border px-2 py-1"
            style={{
              backgroundColor: "var(--card-bg)",
              borderColor: "var(--border)",
              color: "var(--foreground)",
            }}
          >
            {tickers.map((t) => (
              <option key={t} value={t}>
                {t === "ALL" ? "티커: 전체" : `티커: ${t}`}
              </option>
            ))}
          </select>
        )}

        {/* 정렬 */}
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as TradeSortKey)}
          className="rounded border px-2 py-1"
          style={{
            backgroundColor: "var(--card-bg)",
            borderColor: "var(--border)",
            color: "var(--foreground)",
          }}
        >
          <option value="entry">정렬: 진입일</option>
          <option value="exit">정렬: 청산일</option>
          <option value="pnl">정렬: 손익</option>
          <option value="duration">정렬: 보유기간</option>
        </select>
        <button
          type="button"
          onClick={() => setOrder(order === "asc" ? "desc" : "asc")}
          className="rounded border px-2 py-1 transition-colors"
          style={{
            backgroundColor: "var(--card-bg)",
            borderColor: "var(--border)",
            color: "var(--foreground)",
          }}
          title={order === "asc" ? "오름차순" : "내림차순"}
        >
          {order === "asc" ? "↑ 오름" : "↓ 내림"}
        </button>
      </div>

      <div
        className="pretty-scroll overflow-x-auto rounded-md border"
        style={{ borderColor: "var(--border)", maxHeight: "300px", overflowY: "auto" }}
      >
        <table className="w-full text-xs">
          <thead className="sticky top-0" style={{ backgroundColor: "var(--card-bg)" }}>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th className="px-3 py-2 text-left font-medium" style={{ color: "var(--muted)" }}>
                티커
              </th>
              <th className="px-3 py-2 text-left font-medium" style={{ color: "var(--muted)" }}>
                진입
              </th>
              <th className="px-3 py-2 text-left font-medium" style={{ color: "var(--muted)" }}>
                청산
              </th>
              <th className="px-3 py-2 text-right font-medium" style={{ color: "var(--muted)" }}>
                보유(일)
              </th>
              <th className="px-3 py-2 text-right font-medium" style={{ color: "var(--muted)" }}>
                손익
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((trade, idx) => {
              const isProfitable = trade.pnl >= 0;
              return (
                <tr key={idx} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2 font-semibold" style={{ color: "var(--foreground)" }}>
                    {trade.ticker}
                  </td>
                  <td className="px-3 py-2 font-mono" style={{ color: "var(--muted)" }}>
                    {trade.entry_time.slice(0, 10)}
                  </td>
                  <td className="px-3 py-2 font-mono" style={{ color: "var(--muted)" }}>
                    {trade.exit_time.slice(0, 10)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono" style={{ color: "var(--muted)" }}>
                    {holdingDays(trade).toFixed(0)}
                  </td>
                  <td
                    className="px-3 py-2 text-right font-mono font-semibold"
                    style={{ color: isProfitable ? "var(--success)" : "var(--danger)" }}
                  >
                    {isProfitable ? "+" : ""}
                    {trade.pnl.toFixed(2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 서브 컴포넌트: 신호 요약 ──────────────────────────────────────────────

function SignalsSummary({ signalsCount }: { signalsCount: SignalsCount }) {
  const total = signalsCount.long + signalsCount.short + signalsCount.exit;
  return (
    <p className="text-xs font-mono" style={{ color: "var(--muted)" }}>
      신호 합계: {total}개 (롱 {signalsCount.long} / 숏 {signalsCount.short} / 청산 {signalsCount.exit})
    </p>
  );
}

// ── 서브 컴포넌트: 설정 에코 ─────────────────────────────────────────────

function ConfigEchoSection({ config }: { config: BacktestConfigEcho }) {
  const items: Array<[string, string]> = [
    ["Sizer", config.sizer],
    ["Lookback", String(config.lookback)],
    ["Entry/Exit", `${config.entry} / ${config.exit}`],
    ["Initial", config.initial.toLocaleString()],
    ["Fee/Slippage", `${config.fee} / ${config.slippage}`],
    ["RFR", config.rfr.toString()],
    ["MaxPosW", config.max_position_weight.toString()],
    ["CashBuf", config.cash_buffer.toString()],
  ];
  return (
    <div
      className="flex flex-wrap gap-2 rounded-md border px-3 py-2 text-xs font-mono"
      style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
    >
      {items.map(([k, v]) => (
        <span key={k} style={{ color: "var(--muted)" }}>
          {k}: <span style={{ color: "var(--foreground)" }}>{v}</span>
        </span>
      ))}
    </div>
  );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────

export interface BacktestResultProps {
  result: BacktestResponse;
}

/**
 * 백테스트 결과 전체를 렌더한다.
 * Metrics 카드 + 자본 곡선 LineChart + 거래 테이블 + 신호 요약으로 구성된다.
 */
export default function BacktestResult({ result }: BacktestResultProps) {
  return (
    <div className="flex flex-col gap-6">
      {/* 페어 헤더 */}
      <div className="flex items-center gap-2">
        <span
          className="rounded px-2 py-0.5 text-xs font-bold font-mono"
          style={{ backgroundColor: "rgba(56,189,248,0.15)", color: "var(--accent)" }}
        >
          {result.pair.a}
        </span>
        <span style={{ color: "var(--muted)" }}>vs</span>
        <span
          className="rounded px-2 py-0.5 text-xs font-bold font-mono"
          style={{ backgroundColor: "rgba(56,189,248,0.15)", color: "var(--accent)" }}
        >
          {result.pair.b}
        </span>
      </div>

      <ConfigEchoSection config={result.config} />
      <MetricsSection metrics={result.metrics} />
      <EquityCurveChart equityCurve={result.equity_curve} />
      <TradesTable trades={result.trades} />
      <SignalsSummary signalsCount={result.signals_count} />
    </div>
  );
}
