"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import ParamHelp from "../_components/ParamHelp";
import SymbolSelect from "../_components/SymbolSelect";

// ── 상수 ──────────────────────────────────────────────────────────────────

const MIN_TRADE_DEFAULT = 0.01;
const WEIGHT_MAX = 1.0;
const DELTA_WEIGHT_DECIMAL = 4;

// ── 타입 정의 ──────────────────────────────────────────────────────────────

/** 현재 보유 포지션 행 */
interface PositionRow {
  id: number;
  symbol: string;
  quantity: number;
  market_value: number;
}

/** 목표 가중치 행 */
interface TargetRow {
  id: number;
  symbol: string;
  weight: number;
}

/** 백엔드 POST /portfolio/rebalance 응답 단일 항목 */
interface OrderIntentItem {
  symbol: string;
  delta_weight: number;
  side: "BUY" | "SELL";
}

/** 백엔드 응답 전체 */
interface RebalanceResponse {
  intents: OrderIntentItem[];
}

// ── 헬퍼 ──────────────────────────────────────────────────────────────────

/** 고유 ID 생성기 (단순 증가 카운터) */
let _nextId = 1;
function genId(): number {
  return _nextId++;
}

/** 목표 가중치 합계를 계산한다 */
function sumWeights(targets: TargetRow[]): number {
  return targets.reduce((acc, row) => acc + row.weight, 0);
}

// ── 서브 컴포넌트: 개인 전용 고지 배너 ───────────────────────────────────

function DisclaimerBanner() {
  // ADR-000: 개인 전용 고지 문구는 반드시 상단에 표시해야 한다.
  return (
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

// ── 서브 컴포넌트: 에러 배너 ──────────────────────────────────────────────

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      className="rounded-md border px-4 py-3 text-sm"
      style={{
        borderColor: "var(--danger)",
        color: "var(--danger)",
        backgroundColor: "rgba(248,113,113,0.08)",
      }}
    >
      오류: {message}
    </div>
  );
}

// ── 서브 컴포넌트: 현재 포지션 테이블 ────────────────────────────────────

interface PositionTableProps {
  rows: PositionRow[];
  onAdd: () => void;
  onRemove: (id: number) => void;
  onChange: (id: number, field: keyof Omit<PositionRow, "id">, value: string) => void;
}

function PositionTable({ rows, onAdd, onRemove, onChange }: PositionTableProps) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
          현재 포지션
        </span>
        <button
          type="button"
          onClick={onAdd}
          className="rounded px-3 py-1 text-xs font-medium border transition-opacity hover:opacity-80"
          style={{
            borderColor: "var(--accent)",
            color: "var(--accent)",
            backgroundColor: "rgba(56,189,248,0.08)",
          }}
        >
          행 추가
        </button>
      </div>

      <div className="pretty-scroll overflow-x-auto rounded-md border" style={{ borderColor: "var(--border)" }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ backgroundColor: "var(--card-bg)", borderBottom: `1px solid var(--border)` }}>
              <th className="px-3 py-2 text-left font-medium" style={{ color: "var(--muted)" }}>심볼</th>
              <th className="px-3 py-2 text-left font-medium" style={{ color: "var(--muted)" }}>수량</th>
              <th className="px-3 py-2 text-left font-medium" style={{ color: "var(--muted)" }}>시장가치</th>
              <th className="px-3 py-2 text-center font-medium" style={{ color: "var(--muted)" }}>삭제</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                <td className="px-3 py-2">
                  <SymbolSelect
                    value={row.symbol}
                    onChange={(v) => onChange(row.id, "symbol", v)}
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    value={row.quantity}
                    min={0}
                    step={1}
                    onChange={(e) => onChange(row.id, "quantity", e.target.value)}
                    className="w-full rounded border px-2 py-1 text-xs"
                    style={{
                      backgroundColor: "var(--card-bg)",
                      borderColor: "var(--border)",
                      color: "var(--foreground)",
                    }}
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    value={row.market_value}
                    min={0}
                    step={0.01}
                    onChange={(e) => onChange(row.id, "market_value", e.target.value)}
                    className="w-full rounded border px-2 py-1 text-xs"
                    style={{
                      backgroundColor: "var(--card-bg)",
                      borderColor: "var(--border)",
                      color: "var(--foreground)",
                    }}
                  />
                </td>
                <td className="px-3 py-2 text-center">
                  <button
                    type="button"
                    onClick={() => onRemove(row.id)}
                    className="rounded px-2 py-0.5 text-xs transition-opacity hover:opacity-80"
                    style={{ color: "var(--danger)" }}
                  >
                    삭제
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-4 text-center text-xs" style={{ color: "var(--muted)" }}>
                  행 추가 버튼으로 포지션을 입력하세요.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 서브 컴포넌트: 목표 가중치 테이블 ────────────────────────────────────

interface TargetTableProps {
  rows: TargetRow[];
  onAdd: () => void;
  onRemove: (id: number) => void;
  onChange: (id: number, field: keyof Omit<TargetRow, "id">, value: string) => void;
}

function TargetTable({ rows, onAdd, onRemove, onChange }: TargetTableProps) {
  const total = sumWeights(rows);
  const isOver = total > WEIGHT_MAX + 0.0001;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
          목표 가중치
        </span>
        <div className="flex items-center gap-3">
          {/* WHY: 합계가 1을 초과하면 빨간색으로 경고해 사용자가 즉시 인식하게 한다 */}
          <span
            className="text-xs font-mono"
            style={{ color: isOver ? "var(--danger)" : "var(--muted)" }}
          >
            합계: {total.toFixed(4)}
            {isOver && " — 1.0 초과"}
          </span>
          <button
            type="button"
            onClick={onAdd}
            className="rounded px-3 py-1 text-xs font-medium border transition-opacity hover:opacity-80"
            style={{
              borderColor: "var(--accent)",
              color: "var(--accent)",
              backgroundColor: "rgba(56,189,248,0.08)",
            }}
          >
            행 추가
          </button>
        </div>
      </div>

      <div className="pretty-scroll overflow-x-auto rounded-md border" style={{ borderColor: "var(--border)" }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ backgroundColor: "var(--card-bg)", borderBottom: `1px solid var(--border)` }}>
              <th className="px-3 py-2 text-left font-medium" style={{ color: "var(--muted)" }}>심볼</th>
              <th className="px-3 py-2 text-left font-medium" style={{ color: "var(--muted)" }}>비중 (0~1)</th>
              <th className="px-3 py-2 text-center font-medium" style={{ color: "var(--muted)" }}>삭제</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                <td className="px-3 py-2">
                  <SymbolSelect
                    value={row.symbol}
                    onChange={(v) => onChange(row.id, "symbol", v)}
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    value={row.weight}
                    min={0}
                    max={WEIGHT_MAX}
                    step={0.01}
                    onChange={(e) => onChange(row.id, "weight", e.target.value)}
                    className="w-full rounded border px-2 py-1 text-xs"
                    style={{
                      backgroundColor: "var(--card-bg)",
                      borderColor: "var(--border)",
                      color: "var(--foreground)",
                    }}
                  />
                </td>
                <td className="px-3 py-2 text-center">
                  <button
                    type="button"
                    onClick={() => onRemove(row.id)}
                    className="rounded px-2 py-0.5 text-xs transition-opacity hover:opacity-80"
                    style={{ color: "var(--danger)" }}
                  >
                    삭제
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-4 text-center text-xs" style={{ color: "var(--muted)" }}>
                  행 추가 버튼으로 목표 비중을 입력하세요.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 서브 컴포넌트: 주문 의도 결과 테이블 ─────────────────────────────────

interface ResultTableProps {
  intents: OrderIntentItem[];
}

function ResultTable({ intents }: ResultTableProps) {
  if (intents.length === 0) {
    return (
      <p className="text-center text-sm py-4" style={{ color: "var(--muted)" }}>
        임계값 미만 또는 이미 균형 상태입니다. 주문이 필요하지 않습니다.
      </p>
    );
  }

  return (
    <div className="pretty-scroll overflow-x-auto rounded-md border" style={{ borderColor: "var(--border)" }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ backgroundColor: "var(--card-bg)", borderBottom: `1px solid var(--border)` }}>
            <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--muted)" }}>심볼</th>
            <th className="px-4 py-3 text-center font-medium" style={{ color: "var(--muted)" }}>방향</th>
            <th className="px-4 py-3 text-right font-medium" style={{ color: "var(--muted)" }}>비중 변화 (%)</th>
          </tr>
        </thead>
        <tbody>
          {intents.map((intent) => (
            <IntentRow key={intent.symbol} intent={intent} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** 단일 주문 의도 행 */
function IntentRow({ intent }: { intent: OrderIntentItem }) {
  const isBuy = intent.side === "BUY";
  const sideColor = isBuy ? "var(--success)" : "var(--danger)";
  const sideBg = isBuy ? "rgba(74,222,128,0.15)" : "rgba(248,113,113,0.15)";
  const deltaPercent = (intent.delta_weight * 100).toFixed(DELTA_WEIGHT_DECIMAL);

  return (
    <tr className="border-t" style={{ borderColor: "var(--border)" }}>
      <td className="px-4 py-3 font-semibold" style={{ color: "var(--foreground)" }}>
        {intent.symbol}
      </td>
      <td className="px-4 py-3 text-center">
        <span
          className="rounded px-2 py-0.5 text-xs font-medium"
          style={{ backgroundColor: sideBg, color: sideColor }}
        >
          {intent.side}
        </span>
      </td>
      <td className="px-4 py-3 text-right font-mono" style={{ color: "var(--accent)" }}>
        {isBuy ? "+" : ""}{deltaPercent}%
      </td>
    </tr>
  );
}

// ── API 호출 헬퍼 ──────────────────────────────────────────────────────────

interface RebalancePayload {
  positions: PositionRow[];
  targets: TargetRow[];
  totalEquity: number;
  minTradeWeight: number;
  maxPositionWeight: number | null;
  cashBuffer: number | null;
}

/** 백엔드 RebalanceRequest 형태로 변환하여 POST 한다 */
async function callRebalanceApi(payload: RebalancePayload): Promise<RebalanceResponse> {
  const body = {
    current_positions: payload.positions.map((p) => ({
      symbol: p.symbol,
      quantity: p.quantity,
      market_value: p.market_value,
    })),
    target_weights: payload.targets.map((t) => ({
      symbol: t.symbol,
      weight: t.weight,
    })),
    total_equity: payload.totalEquity,
    min_trade_weight: payload.minTradeWeight,
    max_position_weight: payload.maxPositionWeight,
    cash_buffer: payload.cashBuffer,
  };

  // next.config.ts rewrites 를 통해 백엔드(localhost:8000)로 프록시된다.
  const response = await fetch("/api/portfolio/rebalance", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`서버 오류 ${response.status}: ${text}`);
  }

  return response.json() as Promise<RebalanceResponse>;
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────

export default function RebalancePage() {
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [targets, setTargets] = useState<TargetRow[]>([]);
  const [totalEquity, setTotalEquity] = useState<number>(0);
  const [minTradeWeight, setMinTradeWeight] = useState<number>(MIN_TRADE_DEFAULT);
  const [maxPositionWeight, setMaxPositionWeight] = useState<string>("");
  const [cashBuffer, setCashBuffer] = useState<string>("");

  const [result, setResult] = useState<RebalanceResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // WHY: 제출 여부를 별도로 추적해 빈 결과와 미제출 상태를 구분한다
  const [hasSubmitted, setHasSubmitted] = useState(false);

  // ── 포지션 핸들러 ──────────────────────────────────────────────────────

  function addPosition() {
    setPositions((prev) => [...prev, { id: genId(), symbol: "", quantity: 0, market_value: 0 }]);
  }

  function removePosition(id: number) {
    setPositions((prev) => prev.filter((row) => row.id !== id));
  }

  function changePosition(id: number, field: keyof Omit<PositionRow, "id">, value: string) {
    setPositions((prev) =>
      prev.map((row) =>
        row.id !== id
          ? row
          : { ...row, [field]: field === "symbol" ? value : Number(value) }
      )
    );
  }

  // ── 목표 가중치 핸들러 ────────────────────────────────────────────────

  function addTarget() {
    setTargets((prev) => [...prev, { id: genId(), symbol: "", weight: 0 }]);
  }

  function removeTarget(id: number) {
    setTargets((prev) => prev.filter((row) => row.id !== id));
  }

  function changeTarget(id: number, field: keyof Omit<TargetRow, "id">, value: string) {
    setTargets((prev) =>
      prev.map((row) =>
        row.id !== id
          ? row
          : { ...row, [field]: field === "symbol" ? value : Number(value) }
      )
    );
  }

  // ── 폼 제출 ───────────────────────────────────────────────────────────

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setResult(null);
    setHasSubmitted(true);

    try {
      const data = await callRebalanceApi({
        positions,
        targets,
        totalEquity,
        minTradeWeight,
        maxPositionWeight: maxPositionWeight === "" ? null : Number(maxPositionWeight),
        cashBuffer: cashBuffer === "" ? null : Number(cashBuffer),
      });
      setResult(data);
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

      <ParamHelp keys={["max_position_weight", "cash_buffer", "initial"]} />

      {/* 상단 내비게이션 */}
      <div className="flex gap-3">
        <Link
          href="/"
          className="self-start rounded-md border px-3 py-1.5 text-sm font-medium transition-opacity hover:opacity-80"
          style={{
            borderColor: "var(--border)",
            color: "var(--muted)",
            backgroundColor: "var(--card-bg)",
          }}
        >
          홈으로
        </Link>
        <Link
          href="/backtest"
          className="self-start rounded-md border px-3 py-1.5 text-sm font-medium transition-opacity hover:opacity-80"
          style={{
            borderColor: "var(--accent)",
            color: "var(--accent)",
            backgroundColor: "rgba(56,189,248,0.08)",
          }}
        >
          백테스트 대시보드
        </Link>
      </div>

      {/* 헤더 */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--foreground)" }}>
          리밸런싱 플래너
        </h1>
        <p className="text-xs" style={{ color: "var(--muted)" }}>
          현재 보유 종목과 가고 싶은 목표 비중을 입력하면, 그 차이를 매수/매도 주문 계획으로
          바꿔줍니다.
        </p>
      </div>

      {/* 사용 가이드 — 초보 사용자를 위한 단계별 설명 */}
      <details
        className="rounded-lg border"
        style={{ borderColor: "var(--accent)", backgroundColor: "rgba(56,189,248,0.04)" }}
      >
        <summary
          className="cursor-pointer px-4 py-3 text-sm font-medium"
          style={{ color: "var(--accent)" }}
        >
          ℹ 처음이신가요? — 리밸런싱 플래너 사용법
        </summary>
        <div
          className="flex flex-col gap-3 px-4 py-3 text-xs leading-relaxed"
          style={{ color: "var(--muted)" }}
        >
          <p>
            <b style={{ color: "var(--foreground)" }}>리밸런싱이란?</b> 현재 계좌 상태와 원하는 배분
            사이의 차이를 좁히는 매매 계획입니다. 예: 삼성전자 60%/카카오 40% 를 원하는데 실제로는
            80/20 이면 삼성전자 일부를 팔고 카카오를 사야 합니다. 이 도구는 그 주문을 대신 계산합니다.
          </p>
          <div className="flex flex-col gap-2">
            <p>
              <b style={{ color: "var(--foreground)" }}>① 현재 포지션</b> — 지금 갖고 있는 종목과
              수량·시장가치를 입력합니다. 시장가치 = 수량 × 현재가.
            </p>
            <p>
              <b style={{ color: "var(--foreground)" }}>② 목표 가중치</b> — 최종적으로 원하는 비중을
              0~1 사이 소수로 입력. 모든 목표 비중의 합은 1.0 이하여야 합니다(남는 건 현금).
            </p>
            <p>
              <b style={{ color: "var(--foreground)" }}>③ 실행 파라미터</b> — 총 자본(현금 포함)과
              선택 제약을 설정합니다.
            </p>
            <p>
              <b style={{ color: "var(--foreground)" }}>④ 플랜 생성</b> 버튼을 누르면 종목별로 몇 %
              를 더 사거나(BUY) 팔아야(SELL) 하는지 주문 의도 목록이 나옵니다.
            </p>
          </div>
          <p className="text-[11px]">
            💡 제안: 먼저 홈에서 유사 종목을 찾아보고 → 백테스트로 전략을 검증한 뒤 → 여기서 실제
            계좌의 리밸런싱 주문을 계획하는 흐름을 권장합니다.
          </p>
        </div>
      </details>

      {/* 입력 폼 */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        {/* 단계 1: 현재 포지션 */}
        <section
          className="rounded-lg border p-6"
          style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
        >
          <div className="mb-3 flex items-baseline gap-2">
            <span
              className="flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold"
              style={{ backgroundColor: "var(--accent)", color: "#0f172a" }}
            >
              1
            </span>
            <h2 className="text-base font-semibold" style={{ color: "var(--foreground)" }}>
              현재 보유 종목
            </h2>
            <span className="text-[11px]" style={{ color: "var(--muted)" }}>
              — 내가 지금 갖고 있는 포지션
            </span>
          </div>
          <PositionTable
            rows={positions}
            onAdd={addPosition}
            onRemove={removePosition}
            onChange={changePosition}
          />
        </section>

        {/* 단계 2: 목표 가중치 */}
        <section
          className="rounded-lg border p-6"
          style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
        >
          <div className="mb-3 flex items-baseline gap-2">
            <span
              className="flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold"
              style={{ backgroundColor: "var(--accent)", color: "#0f172a" }}
            >
              2
            </span>
            <h2 className="text-base font-semibold" style={{ color: "var(--foreground)" }}>
              목표 비중
            </h2>
            <span className="text-[11px]" style={{ color: "var(--muted)" }}>
              — 최종적으로 원하는 포트폴리오 (합 ≤ 1.0)
            </span>
          </div>
          <TargetTable
            rows={targets}
            onAdd={addTarget}
            onRemove={removeTarget}
            onChange={changeTarget}
          />
        </section>

        {/* 단계 3: 전역 파라미터 */}
        <section
          className="rounded-lg border p-6"
          style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
        >
          <div className="mb-3 flex items-baseline gap-2">
            <span
              className="flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold"
              style={{ backgroundColor: "var(--accent)", color: "#0f172a" }}
            >
              3
            </span>
            <h2 className="text-base font-semibold" style={{ color: "var(--foreground)" }}>
              실행 파라미터
            </h2>
            <span className="text-[11px]" style={{ color: "var(--muted)" }}>
              — 총 자본과 선택 제약
            </span>
          </div>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                총 자본 (KRW)
              </label>
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>
                현금까지 포함한 계좌 전체 금액. 목표 비중은 이 값의 비율로 계산됩니다.
              </p>
              <input
                type="number"
                min={0}
                step={1000}
                value={totalEquity}
                onChange={(e) => setTotalEquity(Number(e.target.value))}
                className="rounded-md border px-3 py-2 text-sm"
                style={{
                  backgroundColor: "var(--card-bg)",
                  borderColor: "var(--border)",
                  color: "var(--foreground)",
                }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                단일 종목 최대 비중 (선택)
              </label>
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>
                한 종목이 차지할 수 있는 상한. 비우면 제약 없음. 예: 0.3 = 최대 30%.
              </p>
              <input
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={maxPositionWeight}
                placeholder="예: 0.3"
                onChange={(e) => setMaxPositionWeight(e.target.value)}
                className="rounded-md border px-3 py-2 text-sm"
                style={{
                  backgroundColor: "var(--card-bg)",
                  borderColor: "var(--border)",
                  color: "var(--foreground)",
                }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                현금 버퍼 (선택)
              </label>
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>
                총 자본 중 투자하지 않고 남겨둘 현금 비율. 예: 0.1 = 10% 는 현금 유지.
              </p>
              <input
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={cashBuffer}
                placeholder="예: 0.1"
                onChange={(e) => setCashBuffer(e.target.value)}
                className="rounded-md border px-3 py-2 text-sm"
                style={{
                  backgroundColor: "var(--card-bg)",
                  borderColor: "var(--border)",
                  color: "var(--foreground)",
                }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                최소 거래 비중
              </label>
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>
                이 값보다 작은 변화는 무시합니다(잔돈 주문 방지). 예: 0.01 = 1% 미만 변화는 건너뜀.
              </p>
              <input
                type="number"
                min={0}
                max={WEIGHT_MAX}
                step={0.001}
                value={minTradeWeight}
                onChange={(e) => setMinTradeWeight(Number(e.target.value))}
                className="rounded-md border px-3 py-2 text-sm"
                style={{
                  backgroundColor: "var(--card-bg)",
                  borderColor: "var(--border)",
                  color: "var(--foreground)",
                }}
              />
            </div>
          </div>
        </section>

        <button
          type="submit"
          disabled={isLoading}
          className="rounded-md px-4 py-2 text-sm font-semibold transition-opacity disabled:opacity-50"
          style={{ backgroundColor: "var(--accent)", color: "#0f172a" }}
        >
          {isLoading ? "플랜 생성 중..." : "플랜 생성"}
        </button>
      </form>

      {/* 에러 배너 */}
      {error !== null && <ErrorBanner message={error} />}

      {/* 로딩 인디케이터 */}
      {isLoading && (
        <div className="text-center text-sm py-4" style={{ color: "var(--muted)" }}>
          리밸런싱 플랜을 계산하는 중입니다...
        </div>
      )}

      {/* 결과 섹션 */}
      {result !== null && (
        <section className="flex flex-col gap-3">
          <h2 className="text-base font-semibold" style={{ color: "var(--foreground)" }}>
            주문 계획 — {result.intents.length}건
          </h2>
          <ResultTable intents={result.intents} />
        </section>
      )}

      {/* 제출 후 빈 결과 (에러 없음, 로딩 없음, intents=[] 경우는 ResultTable 내부에서 처리) */}
      {hasSubmitted && !isLoading && error === null && result === null && (
        <p className="text-center text-sm py-4" style={{ color: "var(--muted)" }}>
          결과가 없습니다.
        </p>
      )}
    </main>
  );
}
