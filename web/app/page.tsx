"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
// WHY: BlockMath 는 블록 수준 LaTeX 수식을 렌더한다.
//      react-katex 는 KaTeX 위에 React 래퍼만 얹기 때문에 번들 크기 증가가 최소다.
import { BlockMath } from "react-katex";
// WHY: PairChart 는 recharts 를 사용하는 클라이언트 전용 컴포넌트다.
//      같은 "use client" 파일에서 import 하면 번들 경계가 자연스럽게 유지된다.
import PairChart from "./PairChart";
import SymbolPicker from "./_components/SymbolPicker";
import SimilarityHeatmap from "./_components/SimilarityHeatmap";
import ParamHelp from "./_components/ParamHelp";

// ── 타입 정의 ──────────────────────────────────────────────────────────────

type Market = "KRX" | "NASDAQ";

/** 백엔드 /similar/{symbol} 응답의 단일 결과 항목 */
interface SimilarItem {
  rank: number;
  ticker: string;
  score: number;
}

/** 백엔드 /similar/{symbol} 의 응답 스키마 */
interface SimilarResponse {
  target: string;
  results: Array<{ ticker: string; score: number }>;
  /** 백엔드가 실제로 사용한 가중치 (없으면 요청값을 표시) */
  weights?: { w1: number; w2: number; w3: number };
}

/** 탐색 폼의 입력 상태 */
interface SearchForm {
  market: Market;
  symbol: string;
  universe: string;
  as_of: string;
  top_k: number;
}

/** 가중치 슬라이더 상태 */
interface WeightForm {
  w1: number;
  w2: number;
  w3: number;
}

// ── 상수 ──────────────────────────────────────────────────────────────────

const DEFAULT_UNIVERSE = "M1_PLACEHOLDER";
const DEFAULT_TOP_K = 10;
const SCORE_DECIMAL_PLACES = 4;
const WEIGHT_DECIMAL_PLACES = 2;

/** 합 허용 오차: 부동소수점 반올림 오차를 흡수하기 위해 ε을 사용한다 */
const WEIGHT_SUM_EPSILON = 0.005;
const WEIGHT_SUM_TARGET = 1.0;

/**
 * 유사도 점수 공식 (KaTeX LaTeX 문자열).
 * WHY: ADR-002에 따라 공식은 단일 표현식으로 관리하고 UI에서 렌더만 담당한다.
 */
const SIMILARITY_FORMULA_LATEX =
  "\\mathrm{score} = \\mathrm{sign}(\\rho) \\cdot " +
  "(w_1 \\lvert \\rho \\rvert + w_2 \\lvert \\cos\\theta \\rvert + w_3 \\cdot \\mathrm{stability})";

/** 오늘 날짜를 YYYY-MM-DD 형태로 반환한다 (기본 as_of 값) */
function getTodayString(): string {
  return new Date().toISOString().slice(0, 10);
}

// ── 헬퍼: 가중치 합 검증 ─────────────────────────────────────────────────

/**
 * w1+w2+w3 합이 1.0과 ε 이내인지 검사한다.
 * WHY: 합산 후 올림/버림 오차가 ±0.004 범위에서 발생하므로 엄격한 === 비교 대신
 *      WEIGHT_SUM_EPSILON 허용 오차를 적용한다.
 */
function isWeightSumValid(weights: WeightForm): boolean {
  const sum = weights.w1 + weights.w2 + weights.w3;
  return Math.abs(sum - WEIGHT_SUM_TARGET) <= WEIGHT_SUM_EPSILON;
}

/**
 * 현재 w1:w2:w3 비율을 유지하며 합이 정확히 1.0이 되도록 정규화한다.
 * 모든 값이 0이면 균등 분배(1/3)로 초기화한다.
 */
function normalizeWeights(weights: WeightForm): WeightForm {
  const total = weights.w1 + weights.w2 + weights.w3;
  if (total === 0) {
    const equal = parseFloat((WEIGHT_SUM_TARGET / 3).toFixed(WEIGHT_DECIMAL_PLACES));
    return { w1: equal, w2: equal, w3: equal };
  }
  return {
    w1: parseFloat((weights.w1 / total).toFixed(WEIGHT_DECIMAL_PLACES)),
    w2: parseFloat((weights.w2 / total).toFixed(WEIGHT_DECIMAL_PLACES)),
    w3: parseFloat((weights.w3 / total).toFixed(WEIGHT_DECIMAL_PLACES)),
  };
}

// ── 서브 컴포넌트: 경고 배너 ───────────────────────────────────────────────

function DisclaimerBanner() {
  return (
    // ADR-000: 개인 전용 고지 문구는 반드시 상단에 표시해야 한다.
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

// ── 서브 컴포넌트: 가중치 슬라이더 패널 ──────────────────────────────────

interface WeightSliderPanelProps {
  weights: WeightForm;
  onChange: (updated: Partial<WeightForm>) => void;
  onNormalize: () => void;
}

/** 단일 슬라이더 행 (레이블 + 입력 + 값 표시) */
function SliderRow({
  label,
  value,
  onChangeValue,
}: {
  label: string;
  value: number;
  onChangeValue: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <span
        className="w-6 text-sm font-mono font-semibold"
        style={{ color: "var(--accent)" }}
      >
        {label}
      </span>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={value}
        onChange={(e) => onChangeValue(parseFloat(e.target.value))}
        className="flex-1 accent-[var(--accent)]"
      />
      <span
        className="w-10 text-right text-sm font-mono"
        style={{ color: "var(--foreground)" }}
      >
        {value.toFixed(WEIGHT_DECIMAL_PLACES)}
      </span>
    </div>
  );
}

function WeightSliderPanel({ weights, onChange, onNormalize }: WeightSliderPanelProps) {
  const sum = weights.w1 + weights.w2 + weights.w3;
  const isValid = isWeightSumValid(weights);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
          가중치 설정
        </span>
        {/* 합 표시 + 경고 */}
        <span
          className="text-xs font-mono"
          style={{ color: isValid ? "var(--success)" : "var(--danger)" }}
        >
          합계: {sum.toFixed(WEIGHT_DECIMAL_PLACES)}
          {!isValid && " — 합은 1.0 이어야 합니다"}
        </span>
      </div>

      <SliderRow
        label="w1"
        value={weights.w1}
        onChangeValue={(v) => onChange({ w1: v })}
      />
      <SliderRow
        label="w2"
        value={weights.w2}
        onChangeValue={(v) => onChange({ w2: v })}
      />
      <SliderRow
        label="w3"
        value={weights.w3}
        onChangeValue={(v) => onChange({ w3: v })}
      />

      {/* WHY: 슬라이더를 직접 조작하면 합이 1.0을 벗어나기 쉽다.
               정규화 버튼으로 비율을 유지하면서 합을 맞출 수 있게 제공한다. */}
      <button
        type="button"
        onClick={onNormalize}
        className="self-start rounded px-3 py-1 text-xs font-medium border transition-opacity hover:opacity-80"
        style={{
          borderColor: "var(--border)",
          color: "var(--muted)",
          backgroundColor: "var(--card-bg)",
        }}
      >
        정규화 (합 = 1로 자동 조정)
      </button>
    </div>
  );
}

// ── 서브 컴포넌트: 탐색 폼 ────────────────────────────────────────────────

interface SearchFormProps {
  form: SearchForm;
  weights: WeightForm;
  isLoading: boolean;
  isWeightValid: boolean;
  onChange: (updated: Partial<SearchForm>) => void;
  onWeightChange: (updated: Partial<WeightForm>) => void;
  onNormalize: () => void;
  onSubmit: (e: FormEvent) => void;
}

function ExploreForm({
  form,
  weights,
  isLoading,
  isWeightValid,
  onChange,
  onWeightChange,
  onNormalize,
  onSubmit,
}: SearchFormProps) {
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      {/* 심볼 선택 (시장 필터 + 검색 + 드롭다운) */}
      <SymbolPicker
        market={form.market}
        symbol={form.symbol}
        onChange={(next) =>
          onChange({ market: next.market as Market, symbol: next.symbol })
        }
        label="종목 선택 (시장 필터 + 검색)"
      />

      {/* 유니버스는 현재 시드 1종(M1_PLACEHOLDER) 고정. 확장되면 드롭다운으로 교체 */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
          유니버스
        </label>
        <select
          value={form.universe}
          onChange={(e) => onChange({ universe: e.target.value })}
          className="rounded-md border px-3 py-2 text-sm"
          style={{
            backgroundColor: "var(--card-bg)",
            borderColor: "var(--border)",
            color: "var(--foreground)",
          }}
        >
          <option value="M1_PLACEHOLDER">시드 유니버스 (KRX30 + NASDAQ15)</option>
        </select>
      </div>

      {/* 기준일 */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
          기준일 (as_of)
        </label>
        <input
          type="date"
          required
          value={form.as_of}
          onChange={(e) => onChange({ as_of: e.target.value })}
          className="rounded-md border px-3 py-2 text-sm"
          style={{
            backgroundColor: "var(--card-bg)",
            borderColor: "var(--border)",
            color: "var(--foreground)",
          }}
        />
      </div>

      {/* top_k */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
          상위 결과 수 (top_k)
        </label>
        <input
          type="number"
          min={1}
          max={100}
          required
          value={form.top_k}
          onChange={(e) => onChange({ top_k: Number(e.target.value) })}
          className="rounded-md border px-3 py-2 text-sm"
          style={{
            backgroundColor: "var(--card-bg)",
            borderColor: "var(--border)",
            color: "var(--foreground)",
          }}
        />
      </div>

      {/* 가중치 슬라이더 패널 */}
      <div
        className="rounded-md border px-4 py-4"
        style={{ borderColor: "var(--border)", backgroundColor: "rgba(255,255,255,0.03)" }}
      >
        <WeightSliderPanel
          weights={weights}
          onChange={onWeightChange}
          onNormalize={onNormalize}
        />
      </div>

      {/* WHY: 가중치 합이 1.0이 아니면 백엔드에서 의도치 않은 결과가 나오므로
               폼 제출 자체를 비활성화하여 사용자 실수를 원천 차단한다. */}
      <button
        type="submit"
        disabled={isLoading || !isWeightValid}
        className="rounded-md px-4 py-2 text-sm font-semibold transition-opacity disabled:opacity-50"
        style={{
          backgroundColor: "var(--accent)",
          color: "#0f172a",
        }}
      >
        {isLoading ? "탐색 중..." : "유사 종목 탐색"}
      </button>
    </form>
  );
}

// ── 서브 컴포넌트: 결과 테이블 ────────────────────────────────────────────

interface ResultTableProps {
  items: SimilarItem[];
  /** 행 클릭 시 선택된 peer ticker 를 부모에게 전달한다 */
  selectedTicker: string | null;
  onRowClick: (ticker: string) => void;
}

/** 점수가 양수면 초록 배지, 음수면 빨간 배지를 반환한다 */
function ScoreBadge({ score }: { score: number }) {
  const isPositive = score >= 0;
  return (
    <span
      className="rounded px-2 py-0.5 text-xs font-medium"
      style={{
        backgroundColor: isPositive ? "rgba(74,222,128,0.15)" : "rgba(248,113,113,0.15)",
        color: isPositive ? "var(--success)" : "var(--danger)",
      }}
    >
      {isPositive ? "양" : "음"}
    </span>
  );
}

function ResultTable({ items, selectedTicker, onRowClick }: ResultTableProps) {
  if (items.length === 0) return null;

  return (
    <div className="pretty-scroll overflow-x-auto rounded-md border" style={{ borderColor: "var(--border)" }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ backgroundColor: "var(--card-bg)", borderBottom: `1px solid var(--border)` }}>
            <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--muted)" }}>
              순위
            </th>
            <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--muted)" }}>
              티커
            </th>
            <th className="px-4 py-3 text-right font-medium" style={{ color: "var(--muted)" }}>
              유사도 점수
            </th>
            <th className="px-4 py-3 text-center font-medium" style={{ color: "var(--muted)" }}>
              방향
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const isSelected = item.ticker === selectedTicker;
            return (
              <tr
                key={item.ticker}
                // WHY: cursor-pointer + hover 배경으로 행이 클릭 가능함을 명시적으로 전달한다.
                className="border-t cursor-pointer transition-colors"
                style={{
                  borderColor: "var(--border)",
                  // WHY: 선택된 행을 accent 색으로 하이라이트해 현재 차트 대상을 명확히 표시한다.
                  backgroundColor: isSelected ? "rgba(var(--accent-rgb, 56,189,248), 0.12)" : undefined,
                }}
                onClick={() => onRowClick(item.ticker)}
              >
                <td className="px-4 py-3 font-mono" style={{ color: "var(--muted)" }}>
                  {item.rank}
                </td>
                <td className="px-4 py-3 font-semibold" style={{ color: "var(--foreground)" }}>
                  {item.ticker}
                </td>
                <td className="px-4 py-3 text-right font-mono" style={{ color: "var(--accent)" }}>
                  {item.score.toFixed(SCORE_DECIMAL_PLACES)}
                </td>
                <td className="px-4 py-3 text-center">
                  <ScoreBadge score={item.score} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────────────────────

export default function ExplorePage() {
  const [form, setForm] = useState<SearchForm>({
    market: "KRX",
    symbol: "",
    universe: DEFAULT_UNIVERSE,
    as_of: getTodayString(),
    top_k: DEFAULT_TOP_K,
  });

  // WHY: w1=수익률상관, w2=거래량상관, w3=섹터안정성.
  //      기본값 0.5/0.3/0.2는 ADR-002 WeightedSumStrategy 기본 파라미터와 일치한다.
  const [weights, setWeights] = useState<WeightForm>({ w1: 0.5, w2: 0.3, w3: 0.2 });
  const [strategy, setStrategy] = useState<"weighted_sum" | "spearman" | "cointegration">(
    "weighted_sum"
  );

  const [results, setResults] = useState<SimilarItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 응답에서 받은 실제 사용 가중치를 별도로 보관한다
  const [usedWeights, setUsedWeights] = useState<{ w1: number; w2: number; w3: number } | null>(null);
  // WHY: 행 클릭으로 선택된 peer ticker 를 보관해 PairChart 마운트/언마운트를 제어한다.
  //      null 이면 차트 패널을 숨긴다.
  const [selectedPeer, setSelectedPeer] = useState<string | null>(null);
  const [view, setView] = useState<"heatmap" | "table">("heatmap");

  /** 폼 필드 부분 업데이트 핸들러 */
  function handleFormChange(updated: Partial<SearchForm>) {
    setForm((prev) => ({ ...prev, ...updated }));
  }

  /** 가중치 부분 업데이트 핸들러 */
  function handleWeightChange(updated: Partial<WeightForm>) {
    setWeights((prev) => ({ ...prev, ...updated }));
  }

  /** 가중치 정규화 핸들러 */
  function handleNormalize() {
    setWeights(normalizeWeights(weights));
  }

  /** 유사 종목 탐색 API 호출 */
  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setResults([]);
    setUsedWeights(null);
    // WHY: 새 탐색을 시작하면 이전 쌍 차트를 닫아 혼선을 방지한다.
    setSelectedPeer(null);

    try {
      const params = new URLSearchParams({
        market: form.market,
        universe: form.universe,
        as_of: form.as_of,
        top_k: String(form.top_k),
        // WHY: w1/w2/w3 를 쿼리 파라미터로 전달해 백엔드 WeightedSumStrategy를 제어한다.
        w1: String(weights.w1),
        w2: String(weights.w2),
        w3: String(weights.w3),
        strategy,
      });

      // next.config.ts rewrites 를 통해 백엔드(localhost:8000)로 프록시된다.
      const response = await fetch(`/api/similar/${encodeURIComponent(form.symbol)}?${params}`);

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`서버 오류 ${response.status}: ${body}`);
      }

      // WHY: 백엔드는 rank 가 없는 평평한 results 배열을 돌려주므로
      //      UI 측에서 내림차순 |score| 순서대로 rank 를 부여한다.
      const data: SimilarResponse = await response.json();
      const ranked: SimilarItem[] = data.results.map((item, index) => ({
        rank: index + 1,
        ticker: item.ticker,
        score: item.score,
      }));
      setResults(ranked);

      // 백엔드가 weights 필드를 돌려주면 그걸, 아니면 요청값을 표시한다.
      setUsedWeights(data.weights ?? { w1: weights.w1, w2: weights.w2, w3: weights.w3 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다.");
    } finally {
      setIsLoading(false);
    }
  }

  const isWeightValid = isWeightSumValid(weights);

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6">
      {/* ADR-000: 개인 전용 고지 문구 — 페이지 최상단 배치 필수 */}
      <DisclaimerBanner />

      <ParamHelp keys={["lookback"]} />

      {/* WHY: 주요 도구로의 내비게이션을 최상단에 노출해 탐색성을 높인다 */}
      <div className="flex gap-3">
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
        <Link
          href="/rebalance"
          className="self-start rounded-md border px-3 py-1.5 text-sm font-medium transition-opacity hover:opacity-80"
          style={{
            borderColor: "var(--accent)",
            color: "var(--accent)",
            backgroundColor: "rgba(56,189,248,0.08)",
          }}
        >
          리밸런싱 플래너
        </Link>
      </div>

      {/* 헤더 + KaTeX 공식 */}
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--foreground)" }}>
          유사 종목 탐색기
        </h1>
        <p className="text-xs" style={{ color: "var(--muted)" }}>
          Sim Money M1 — 유사도 공식 (ADR-002 WeightedSumStrategy)
        </p>
        {/* WHY: plain-text 수식 대신 KaTeX 렌더로 전환하여 공식 가독성을 높인다. */}
        <div
          className="rounded-md border px-4 py-3 overflow-x-auto"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--card-bg)" }}
        >
          <BlockMath math={SIMILARITY_FORMULA_LATEX} />
        </div>
      </div>

      {/* 탐색 폼 */}
      <section
        className="rounded-lg border p-6"
        style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)" }}
      >
        <div className="mb-4 flex items-center gap-3">
          <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
            유사도 전략
          </label>
          <select
            value={strategy}
            onChange={(e) =>
              setStrategy(e.target.value as "weighted_sum" | "spearman" | "cointegration")
            }
            className="rounded-md border px-3 py-1.5 text-sm"
            style={{
              backgroundColor: "var(--card-bg)",
              borderColor: "var(--border)",
              color: "var(--foreground)",
            }}
          >
            <option value="weighted_sum">weighted_sum (w1/w2/w3)</option>
            <option value="spearman">spearman (순위상관)</option>
            <option value="cointegration">cointegration (Engle-Granger)</option>
          </select>
          {strategy !== "weighted_sum" && (
            <span className="text-xs" style={{ color: "var(--muted)" }}>
              w1/w2/w3 는 무시됩니다
            </span>
          )}
        </div>
        <ExploreForm
          form={form}
          weights={weights}
          isLoading={isLoading}
          isWeightValid={isWeightValid}
          onChange={handleFormChange}
          onWeightChange={handleWeightChange}
          onNormalize={handleNormalize}
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
          백엔드에서 유사도를 계산하는 중입니다...
        </div>
      )}

      {/* 결과 섹션 */}
      {results.length > 0 && (
        <section className="flex flex-col gap-3">
          {/* WHY: 실제 사용된 가중치를 헤더에 표기해 재현성을 확보한다. */}
          <div className="flex flex-col gap-0.5">
            <h2 className="text-base font-semibold" style={{ color: "var(--foreground)" }}>
              유사 종목 결과 — {form.symbol} 기준 상위 {results.length}개
            </h2>
            {usedWeights !== null && (
              <p className="text-xs font-mono" style={{ color: "var(--muted)" }}>
                사용된 가중치: w1={usedWeights.w1.toFixed(WEIGHT_DECIMAL_PLACES)},
                {" "}w2={usedWeights.w2.toFixed(WEIGHT_DECIMAL_PLACES)},
                {" "}w3={usedWeights.w3.toFixed(WEIGHT_DECIMAL_PLACES)}
              </p>
            )}
          </div>
          {/* 뷰 전환 토글 */}
          <div className="flex gap-2 text-xs">
            {(["heatmap", "table"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setView(v)}
                className="rounded border px-3 py-1 transition-opacity"
                style={{
                  borderColor: view === v ? "var(--accent)" : "var(--border)",
                  color: view === v ? "var(--accent)" : "var(--muted)",
                  backgroundColor: view === v ? "rgba(56,189,248,0.1)" : "var(--card-bg)",
                }}
              >
                {v === "heatmap" ? "히트맵" : "테이블"}
              </button>
            ))}
          </div>
          {view === "heatmap" ? (
            <SimilarityHeatmap
              items={results}
              selectedTicker={selectedPeer}
              onRowClick={setSelectedPeer}
            />
          ) : (
            <ResultTable
              items={results}
              selectedTicker={selectedPeer}
              onRowClick={setSelectedPeer}
            />
          )}
        </section>
      )}

      {/* 쌍 시각화 패널
          WHY: selectedPeer 가 null 이 아닐 때만 마운트해 불필요한 API 호출을 막는다.
               ticker 는 "MARKET:SYMBOL" 또는 단순 심볼 형태일 수 있으므로
               콜론 유무를 확인하고 분기한다. */}
      {selectedPeer !== null && (() => {
        const parts = selectedPeer.split(":");
        const hasTwoSegments = parts.length >= 2;
        const marketB = hasTwoSegments ? parts[0] : form.market;
        const symbolB = hasTwoSegments ? parts.slice(1).join(":") : selectedPeer;
        return (
          <PairChart
            market={form.market}
            symbolA={form.symbol}
            marketB={marketB}
            symbolB={symbolB}
            asOf={form.as_of}
          />
        );
      })()}

      {/* 결과 없음 (제출 후 빈 배열) */}
      {!isLoading && results.length === 0 && error === null && form.symbol !== "" && (
        <p className="text-center text-sm py-4" style={{ color: "var(--muted)" }}>
          결과가 없습니다. 심볼 또는 유니버스를 확인하세요.
        </p>
      )}
    </main>
  );
}
