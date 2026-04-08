"use client";

// WHY: fetch, useState, useEffect 등 클라이언트 훅을 직접 사용하므로 "use client" 필수.
import { useState, FormEvent } from "react";
import BacktestResult, { BacktestResponse } from "./BacktestResult";
import SymbolPicker from "../_components/SymbolPicker";
import ParamHelp from "../_components/ParamHelp";

// ── 타입 정의 ──────────────────────────────────────────────────────────────

/** 포지션 사이징 방식 선택지 */
type SizerType = "strength" | "equal_weight" | "score_weighted";

/** 백테스트 폼 입력 상태 */
interface BacktestForm {
  a: string;
  b: string;
  marketA: string;
  marketB: string;
  lookback: number;
  entry: number;
  exit: number;
  initial: number;
  fee: number;
  slippage: number;
  rfr: number;
  sizer: SizerType;
  /** 최대 포지션 비중 — equal_weight 사이저 선택 시에만 의미 있음 */
  maxPositionWeight: number;
  /** 현금 버퍼 비율 — equal_weight 사이저 선택 시에만 의미 있음 */
  cashBuffer: number;
  /** 리스크 가드 — null 이면 비활성. 모두 옵션 (M5 S13) */
  riskPositionLimit: number | null;
  riskMaxDrawdown: number | null;
  riskDailyLoss: number | null;
  /** 단일 포지션 손절률 — ExitAdvisor (M5 S14) */
  riskStopLoss: number | null;
}

// ── 상수 ──────────────────────────────────────────────────────────────────

// 무위험 수익률 최대값 — 현실적 연환산 상한선
const RFR_MAX = 0.2;
// 포트폴리오 제약 입력 스텝 — 5% 단위 조정
const CONSTRAINTS_STEP = 0.05;

const DEFAULT_FORM: BacktestForm = {
  a: "",
  b: "",
  marketA: "KRX",
  marketB: "KRX",
  lookback: 20,
  entry: 1.5,
  exit: 0.5,
  initial: 10_000_000,
  fee: 0.001,
  slippage: 5.0,
  rfr: 0.0,
  sizer: "strength",
  maxPositionWeight: 1.0,
  cashBuffer: 0.0,
  riskPositionLimit: null,
  riskMaxDrawdown: null,
  riskDailyLoss: null,
  riskStopLoss: null,
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

// ── 서브 컴포넌트: 리스크 입력 ────────────────────────────────────────────

interface RiskInputProps {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
}

function RiskInput({ label, value, onChange }: RiskInputProps) {
  // WHY: 빈 문자열 → null, 숫자 → number 로 변환해 미지정 의미를 명확히 한다.
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs" style={{ color: "var(--muted)" }}>{label}</label>
      <input
        type="number"
        step={0.01}
        min={0}
        max={1}
        placeholder="비활성"
        value={value ?? ""}
        onChange={(e) => {
          const raw = e.target.value;
          onChange(raw === "" ? null : Number(raw));
        }}
        className="rounded border px-2 py-1 text-sm"
        style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)", color: "var(--foreground)" }}
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
        <SymbolPicker
          label="종목 A"
          market={form.marketA}
          symbol={form.a}
          onChange={(n) => onChange({ marketA: n.market, a: n.symbol })}
        />
        <SymbolPicker
          label="종목 B"
          market={form.marketB}
          symbol={form.b}
          onChange={(n) => onChange({ marketB: n.market, b: n.symbol })}
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

      {/* 무위험 수익률 + 사이징 방식 — 같은 행에 배치 */}
      <div className="grid grid-cols-3 gap-3">
        <NumberInputRow
          label="무위험 수익률 (연환산)"
          value={form.rfr}
          step={0.01}
          min={0}
          max={RFR_MAX}
          onChange={(v) => onChange({ rfr: v })}
        />
        {/* WHY: 사이징 방식은 포지션 비중 계산 전략을 선택한다.
                 strength=신호 강도 비례(기본), equal_weight=균등 비중 */}
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
            사이징 방식
          </label>
          <select
            value={form.sizer}
            onChange={(e) => onChange({ sizer: e.target.value as SizerType })}
            className="rounded-md border px-3 py-2 text-sm"
            style={{
              backgroundColor: "var(--card-bg)",
              borderColor: "var(--border)",
              color: "var(--foreground)",
            }}
          >
            <option value="strength">신호 강도 비례 (strength)</option>
            <option value="equal_weight">균등 비중 (equal_weight)</option>
          </select>
        </div>
      </div>

      {/* WHY: 포트폴리오 제약 파라미터는 equal_weight 사이저 선택 시에만 의미 있으므로
               조건부로 렌더해 사용자 혼란을 방지한다. */}
      {form.sizer === "equal_weight" && (
        <div className="grid grid-cols-2 gap-3">
          <NumberInputRow
            label="최대 포지션 비중 (0~1)"
            value={form.maxPositionWeight}
            step={CONSTRAINTS_STEP}
            min={CONSTRAINTS_STEP}
            max={1}
            onChange={(v) => onChange({ maxPositionWeight: v })}
          />
          <NumberInputRow
            label="현금 버퍼 (0~1)"
            value={form.cashBuffer}
            step={CONSTRAINTS_STEP}
            min={0}
            max={0.95}
            onChange={(v) => onChange({ cashBuffer: v })}
          />
        </div>
      )}

      {/* WHY: 리스크 가드는 옵션. 접이식 details 로 기본 워크플로 보호 (M5 S13). */}
      <details className="rounded border" style={{ borderColor: "var(--border)" }}>
        <summary className="cursor-pointer px-3 py-2 text-sm font-medium" style={{ color: "var(--foreground)" }}>
          리스크 가드 (선택)
        </summary>
        <div className="grid grid-cols-2 gap-3 p-3">
          <RiskInput
            label="포지션 한도 (0~1)"
            value={form.riskPositionLimit}
            onChange={(v) => onChange({ riskPositionLimit: v })}
          />
          <RiskInput
            label="최대 DD (0~1)"
            value={form.riskMaxDrawdown}
            onChange={(v) => onChange({ riskMaxDrawdown: v })}
          />
          <RiskInput
            label="일일 손실 한도 (0~1)"
            value={form.riskDailyLoss}
            onChange={(v) => onChange({ riskDailyLoss: v })}
          />
          <RiskInput
            label="손절률 — 강제 청산 (0~1)"
            value={form.riskStopLoss}
            onChange={(v) => onChange({ riskStopLoss: v })}
          />
        </div>
      </details>

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
    sizer: form.sizer,
  });
  // WHY: equal_weight 사이저 선택 시에만 제약 파라미터를 쿼리에 포함한다.
  //      다른 사이저에서는 백엔드가 무시하지만 불필요한 파라미터 전송을 줄인다.
  if (form.sizer === "equal_weight") {
    params.set("max_position_weight", String(form.maxPositionWeight));
    params.set("cash_buffer", String(form.cashBuffer));
  }
  // WHY: 리스크 가드 파라미터는 null 이 아닐 때만 쿼리에 포함한다.
  if (form.riskPositionLimit !== null) {
    params.set("risk_position_limit", String(form.riskPositionLimit));
  }
  if (form.riskMaxDrawdown !== null) {
    params.set("risk_max_drawdown", String(form.riskMaxDrawdown));
  }
  if (form.riskDailyLoss !== null) {
    params.set("risk_daily_loss", String(form.riskDailyLoss));
  }
  if (form.riskStopLoss !== null) {
    params.set("risk_stop_loss", String(form.riskStopLoss));
  }
  return `/api/backtest/pair/${encodeURIComponent(form.a)}/${encodeURIComponent(form.b)}?${params}`;
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────

export default function BacktestPage() {
  const [form, setForm] = useState<BacktestForm>(DEFAULT_FORM);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [walkForward, setWalkForward] = useState<{
    in_sample: BacktestResponse;
    out_of_sample: BacktestResponse;
    split: { ratio: number; timestamp: string; index: number };
  } | null>(null);
  const [wfEnabled, setWfEnabled] = useState(false);
  const [splitRatio, setSplitRatio] = useState(0.7);
  // WHY: M4 S7 — k-fold rolling walk-forward UI. wfEnabled 와 상호배타.
  const [kfoldEnabled, setKfoldEnabled] = useState(false);
  const [folds, setFolds] = useState(3);
  const [kfold, setKfold] = useState<{
    folds: number;
    fold_count: number;
    aggregate: {
      avg_is_total_return: number;
      avg_oos_total_return: number;
      avg_is_sharpe: number;
      avg_oos_sharpe: number;
    };
    results: Array<{
      fold: number;
      in_sample: BacktestResponse;
      out_of_sample: BacktestResponse;
    }>;
  } | null>(null);
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
    setWalkForward(null);
    setKfold(null);

    try {
      let url = buildBacktestUrl(form);
      if (kfoldEnabled) {
        url = url.replace(
          `${encodeURIComponent(form.b)}?`,
          `${encodeURIComponent(form.b)}/walk-forward-kfold?folds=${folds}&`
        );
      } else if (wfEnabled) {
        // WHY: walk-forward 엔드포인트는 경로 접미가 /walk-forward 이고 split_ratio 쿼리가 추가된다.
        url = url.replace(
          `${encodeURIComponent(form.b)}?`,
          `${encodeURIComponent(form.b)}/walk-forward?split_ratio=${splitRatio}&`
        );
      }
      const response = await fetch(url);

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`서버 오류 ${response.status}: ${body}`);
      }

      const data = await response.json();
      if (kfoldEnabled) {
        setKfold(data);
      } else if (wfEnabled) {
        setWalkForward(data);
      } else {
        setResult(data as BacktestResponse);
      }
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

      <ParamHelp />

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
        <div className="mb-4 flex items-center gap-3 flex-wrap">
          <label className="flex items-center gap-2 text-sm" style={{ color: "var(--foreground)" }}>
            <input
              type="checkbox"
              checked={wfEnabled}
              onChange={(e) => {
                setWfEnabled(e.target.checked);
                if (e.target.checked) setKfoldEnabled(false);
              }}
            />
            Walk-forward (IS/OOS 분할)
          </label>
          <label className="flex items-center gap-2 text-sm" style={{ color: "var(--foreground)" }}>
            <input
              type="checkbox"
              checked={kfoldEnabled}
              onChange={(e) => {
                setKfoldEnabled(e.target.checked);
                if (e.target.checked) setWfEnabled(false);
              }}
            />
            k-fold rolling
          </label>
          {kfoldEnabled && (
            <label className="flex items-center gap-2 text-sm" style={{ color: "var(--foreground)" }}>
              folds
              <input
                type="number"
                min={2}
                max={10}
                step={1}
                value={folds}
                onChange={(e) => setFolds(Number(e.target.value))}
                className="w-16 rounded border px-2 py-1 text-xs"
                style={{
                  backgroundColor: "var(--card-bg)",
                  borderColor: "var(--border)",
                  color: "var(--foreground)",
                }}
              />
            </label>
          )}
          {wfEnabled && (
            <label className="flex items-center gap-2 text-sm" style={{ color: "var(--foreground)" }}>
              split_ratio
              <input
                type="number"
                min={0.1}
                max={0.9}
                step={0.05}
                value={splitRatio}
                onChange={(e) => setSplitRatio(Number(e.target.value))}
                className="w-20 rounded border px-2 py-1 text-xs"
                style={{
                  backgroundColor: "var(--card-bg)",
                  borderColor: "var(--border)",
                  color: "var(--foreground)",
                }}
              />
            </label>
          )}
        </div>
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

      {/* k-fold 결과 — 폴드별 IS/OOS 카드 + 평균 집계 */}
      {kfold !== null && (
        <>
          <div className="rounded-lg border p-4 text-sm" style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)", color: "var(--foreground)" }}>
            <div className="font-semibold mb-2">k-fold 평균 ({kfold.fold_count} folds, requested={kfold.folds})</div>
            <div className="grid grid-cols-2 gap-2 font-mono text-xs" style={{ color: "var(--muted)" }}>
              <div>avg IS total return: {kfold.aggregate.avg_is_total_return.toFixed(4)}</div>
              <div>avg OOS total return: {kfold.aggregate.avg_oos_total_return.toFixed(4)}</div>
              <div>avg IS sharpe: {kfold.aggregate.avg_is_sharpe.toFixed(4)}</div>
              <div>avg OOS sharpe: {kfold.aggregate.avg_oos_sharpe.toFixed(4)}</div>
            </div>
          </div>
          {kfold.results.map((fr) => (
            <section
              key={fr.fold}
              className="rounded-lg border p-6 flex flex-col gap-4"
              style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
            >
              <div className="text-sm font-semibold" style={{ color: "var(--accent)" }}>
                Fold #{fr.fold}
              </div>
              <div>
                <div className="text-xs mb-1" style={{ color: "var(--muted)" }}>In-sample</div>
                <BacktestResult result={fr.in_sample} />
              </div>
              <div>
                <div className="text-xs mb-1" style={{ color: "var(--muted)" }}>Out-of-sample</div>
                <BacktestResult result={fr.out_of_sample} />
              </div>
            </section>
          ))}
        </>
      )}

      {/* Walk-forward 결과 — IS/OOS 병렬 표시 */}
      {walkForward !== null && (
        <>
          <div className="text-xs font-mono" style={{ color: "var(--muted)" }}>
            split @ {walkForward.split.timestamp} (ratio {walkForward.split.ratio}, idx{" "}
            {walkForward.split.index})
          </div>
          <section
            className="rounded-lg border p-6"
            style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
          >
            <h3 className="mb-3 text-sm font-semibold" style={{ color: "var(--accent)" }}>
              In-sample
            </h3>
            <BacktestResult result={walkForward.in_sample} />
          </section>
          <section
            className="rounded-lg border p-6"
            style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
          >
            <h3 className="mb-3 text-sm font-semibold" style={{ color: "var(--accent)" }}>
              Out-of-sample
            </h3>
            <BacktestResult result={walkForward.out_of_sample} />
          </section>
        </>
      )}
    </main>
  );
}
