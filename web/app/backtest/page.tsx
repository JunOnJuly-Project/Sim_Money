"use client";

// WHY: fetch, useState, useEffect 등 클라이언트 훅을 직접 사용하므로 "use client" 필수.
import { useState, FormEvent } from "react";
import BacktestResult, { BacktestResponse } from "./BacktestResult";

// ── 타입 정의 ──────────────────────────────────────────────────────────────

/** 백테스트 폼 입력 상태 */
interface BacktestForm {
  a: string;
  b: string;
  lookback: number;
  entry: number;
  exit: number;
  initial: number;
  fee: number;
  slippage: number;
  rfr: number;
}

// ── 상수 ──────────────────────────────────────────────────────────────────

// 무위험 수익률 최대값 — 현실적 연환산 상한선
const RFR_MAX = 0.2;

const DEFAULT_FORM: BacktestForm = {
  a: "",
  b: "",
  lookback: 20,
  entry: 1.5,
  exit: 0.5,
  initial: 10000,
  fee: 0.001,
  slippage: 5.0,
  rfr: 0.0,
};

// ── 서브 컴포넌트: 고지 배너 ──────────────────────────────────────────────

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
      백테스트는 과거 데이터 추정치입니다. 본인 전용 연구용이며 투자 조언이 아닙니다.
    </div>
  );
}

// ── 서브 컴포넌트: 숫자 입력 행 ──────────────────────────────────────────

interface NumberInputRowProps {
  label: string;
  value: number;
  step?: number;
  min?: number;
  max?: number;
  onChange: (v: number) => void;
}

function NumberInputRow({ label, value, step = 1, min = 0, max, onChange }: NumberInputRowProps) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
        {label}
      </label>
      <input
        type="number"
        step={step}
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="rounded-md border px-3 py-2 text-sm"
        style={{
          backgroundColor: "var(--card-bg)",
          borderColor: "var(--border)",
          color: "var(--foreground)",
        }}
      />
    </div>
  );
}

// ── 서브 컴포넌트: 심볼 입력 행 ──────────────────────────────────────────

interface TextInputRowProps {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
}

function TextInputRow({ label, placeholder, value, onChange }: TextInputRowProps) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
        {label}
      </label>
      <input
        type="text"
        required
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value.trim())}
        className="rounded-md border px-3 py-2 text-sm"
        style={{
          backgroundColor: "var(--card-bg)",
          borderColor: "var(--border)",
          color: "var(--foreground)",
        }}
      />
    </div>
  );
}

// ── 서브 컴포넌트: 백테스트 폼 ───────────────────────────────────────────

interface BacktestFormProps {
  form: BacktestForm;
  isLoading: boolean;
  onChange: (updated: Partial<BacktestForm>) => void;
  onSubmit: (e: FormEvent) => void;
}

function BacktestForm({ form, isLoading, onChange, onSubmit }: BacktestFormProps) {
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      {/* 종목 심볼 — 좌우 배치 */}
      <div className="grid grid-cols-2 gap-3">
        <TextInputRow
          label="종목 A"
          placeholder="예: 005930"
          value={form.a}
          onChange={(v) => onChange({ a: v })}
        />
        <TextInputRow
          label="종목 B"
          placeholder="예: 000660"
          value={form.b}
          onChange={(v) => onChange({ b: v })}
        />
      </div>

      {/* 신호 파라미터 */}
      <div className="grid grid-cols-3 gap-3">
        <NumberInputRow
          label="Lookback (일)"
          value={form.lookback}
          step={1}
          min={5}
          onChange={(v) => onChange({ lookback: v })}
        />
        <NumberInputRow
          label="진입 임계값 (σ)"
          value={form.entry}
          step={0.1}
          min={0.1}
          onChange={(v) => onChange({ entry: v })}
        />
        <NumberInputRow
          label="청산 임계값 (σ)"
          value={form.exit}
          step={0.1}
          min={0}
          onChange={(v) => onChange({ exit: v })}
        />
      </div>

      {/* 자본/비용 파라미터 */}
      <div className="grid grid-cols-3 gap-3">
        <NumberInputRow
          label="초기 자본"
          value={form.initial}
          step={1000}
          min={1}
          onChange={(v) => onChange({ initial: v })}
        />
        <NumberInputRow
          label="수수료율 (소수)"
          value={form.fee}
          step={0.0001}
          min={0}
          onChange={(v) => onChange({ fee: v })}
        />
        <NumberInputRow
          label="슬리피지 (bps)"
          value={form.slippage}
          step={1}
          min={0}
          onChange={(v) => onChange({ slippage: v })}
        />
      </div>

      {/* 무위험 수익률 — Sharpe 비율 계산 기준선 */}
      <div className="grid grid-cols-3 gap-3">
        <NumberInputRow
          label="무위험 수익률 (연환산)"
          value={form.rfr}
          step={0.01}
          min={0}
          max={RFR_MAX}
          onChange={(v) => onChange({ rfr: v })}
        />
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="rounded-md px-4 py-2 text-sm font-semibold transition-opacity disabled:opacity-50"
        style={{ backgroundColor: "var(--accent)", color: "#0f172a" }}
      >
        {isLoading ? "백테스트 실행 중..." : "백테스트 실행"}
      </button>
    </form>
  );
}

// ── API 호출 헬퍼 ──────────────────────────────────────────────────────────

/**
 * 백테스트 API URL 을 조립한다.
 * WHY: 쿼리 파라미터 이름이 백엔드 엔드포인트 시그니처와 정확히 일치해야 한다.
 *      exit 는 FastAPI 예약어와 충돌해 alias="exit" 로 선언돼 있으므로
 *      쿼리 파라미터 키를 "exit" 로 사용한다.
 */
function buildBacktestUrl(form: BacktestForm): string {
  const params = new URLSearchParams({
    lookback: String(form.lookback),
    entry: String(form.entry),
    exit: String(form.exit),
    initial: String(form.initial),
    fee: String(form.fee),
    slippage: String(form.slippage),
    rfr: String(form.rfr),
  });
  return `/api/backtest/pair/${encodeURIComponent(form.a)}/${encodeURIComponent(form.b)}?${params}`;
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────

export default function BacktestPage() {
  const [form, setForm] = useState<BacktestForm>(DEFAULT_FORM);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFormChange(updated: Partial<BacktestForm>) {
    setForm((prev) => ({ ...prev, ...updated }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const url = buildBacktestUrl(form);
      const response = await fetch(url);

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`서버 오류 ${response.status}: ${body}`);
      }

      const data: BacktestResponse = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6">
      {/* ADR-000: 개인 전용 고지 문구 — 최상단 필수 */}
      <DisclaimerBanner />

      {/* 헤더 */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--foreground)" }}>
          백테스트 대시보드
        </h1>
        <p className="text-xs" style={{ color: "var(--muted)" }}>
          Sim Money M2 — 페어 트레이딩 z-score 전략 백테스트
        </p>
      </div>

      {/* 폼 섹션 */}
      <section
        className="rounded-lg border p-6"
        style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
      >
        <BacktestForm
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
          백테스트 실행 중...
        </div>
      )}

      {/* 결과 섹션 */}
      {result !== null && (
        <section
          className="rounded-lg border p-6"
          style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
        >
          <BacktestResult result={result} />
        </section>
      )}
    </main>
  );
}
