"use client";

// WHY: 탐색/백테스트/리밸런싱 페이지가 각자 심볼을 텍스트로 입력받던 구조는
//      오타·시장 혼동·유니버스 불일치를 자주 일으켰다. /meta/universe 에서
//      시드된 실제 종목 목록을 받아 시장 필터 + 검색 + 선택 UX 로 통일한다.

import { useEffect, useMemo, useState } from "react";

interface UniverseItem {
  symbol: string;
  market: string;
}

interface UniverseMetaResponse {
  name: string;
  total: number;
  markets: string[];
  by_market: Record<string, UniverseItem[]>;
}

// WHY: KRX 숫자 코드는 사람에게 불친절하므로 가장 많이 쓰이는 30종목 한글명을
//      프런트 상수로 보강한다. API 에서 내려줘야 하는 완전한 맵은 M6 후속 스콥.
const _KRX_NAMES: Record<string, string> = {
  "005930": "삼성전자",
  "000660": "SK하이닉스",
  "373220": "LG에너지솔루션",
  "207940": "삼성바이오로직스",
  "005380": "현대차",
  "000270": "기아",
  "005490": "POSCO홀딩스",
  "051910": "LG화학",
  "006400": "삼성SDI",
  "035420": "NAVER",
  "035720": "카카오",
  "068270": "셀트리온",
  "055550": "신한지주",
  "105560": "KB금융",
  "086790": "하나금융지주",
  "316140": "우리금융지주",
  "138040": "메리츠금융지주",
  "032830": "삼성생명",
  "015760": "한국전력",
  "017670": "SK텔레콤",
  "030200": "KT",
  "033780": "KT&G",
  "003550": "LG",
  "009150": "삼성전기",
  "066570": "LG전자",
  "010130": "고려아연",
  "011200": "HMM",
  "028260": "삼성물산",
  "251270": "넷마블",
  "036570": "엔씨소프트",
};

export function formatTickerLabel(market: string, symbol: string): string {
  if (market === "KRX" && _KRX_NAMES[symbol]) {
    return `${_KRX_NAMES[symbol]} (${symbol})`;
  }
  return symbol;
}

interface SymbolPickerProps {
  /** 현재 선택된 시장 */
  market: string;
  /** 현재 선택된 심볼 */
  symbol: string;
  /** 시장+심볼이 변경되면 호출 */
  onChange: (next: { market: string; symbol: string }) => void;
  /** 라벨 */
  label?: string;
  /** 시장 필터 활성화 여부 (false 면 모든 시장 통합 표시) */
  showMarketFilter?: boolean;
}

/**
 * 공용 심볼 선택기.
 *
 * - /meta/universe 에서 시드 종목 목록을 즉시 로드
 * - 시장 필터 + 검색어 필터 + 드롭다운 선택
 * - KRX 는 한글 종목명을 함께 표시
 */
export default function SymbolPicker({
  market,
  symbol,
  onChange,
  label = "종목",
  showMarketFilter = true,
}: SymbolPickerProps) {
  const [meta, setMeta] = useState<UniverseMetaResponse | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch("/api/meta/universe")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: UniverseMetaResponse) => {
        if (!alive) return;
        setMeta(data);
        setError(null);
      })
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  const availableMarkets = meta?.markets ?? [];
  const items: UniverseItem[] = useMemo(() => {
    if (!meta) return [];
    const source = showMarketFilter ? meta.by_market[market] ?? [] : Object.values(meta.by_market).flat();
    if (!query.trim()) return source;
    const q = query.toLowerCase();
    return source.filter((it) => {
      const label = formatTickerLabel(it.market, it.symbol).toLowerCase();
      return label.includes(q) || it.symbol.toLowerCase().includes(q);
    });
  }, [meta, market, query, showMarketFilter]);

  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
        {label}
      </label>

      {showMarketFilter && (
        <div className="flex gap-2">
          {availableMarkets.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => onChange({ market: m, symbol: "" })}
              className="rounded border px-3 py-1 text-xs transition-opacity"
              style={{
                borderColor: market === m ? "var(--accent)" : "var(--border)",
                color: market === m ? "var(--accent)" : "var(--muted)",
                backgroundColor: market === m ? "rgba(56,189,248,0.1)" : "var(--card-bg)",
              }}
            >
              {m}
            </button>
          ))}
        </div>
      )}

      <input
        type="text"
        placeholder="검색 (종목명 또는 코드)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="rounded border px-3 py-2 text-sm"
        style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border)", color: "var(--foreground)" }}
      />

      {loading && (
        <p className="text-xs" style={{ color: "var(--muted)" }}>
          유니버스 로드 중...
        </p>
      )}
      {error !== null && (
        <p className="text-xs" style={{ color: "var(--danger)" }}>
          유니버스 로드 실패: {error}
        </p>
      )}

      {/* WHY: 스크롤 리스트 대신 칩(chip) 그리드 — 라디오 버튼 UX 에 가까워 선택 상태가
               명확하다. 종목이 많으면 pretty-scroll 로 세로 스크롤 허용. */}
      <div
        className="pretty-scroll max-h-60 overflow-y-auto rounded-lg border p-2"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--card-bg)" }}
      >
        {items.length === 0 && !loading ? (
          <p className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
            결과 없음
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
            {items.map((it) => {
              const isSelected = it.symbol === symbol && it.market === market;
              return (
                <button
                  key={`${it.market}:${it.symbol}`}
                  type="button"
                  onClick={() => onChange({ market: it.market, symbol: it.symbol })}
                  className="group flex items-center gap-1.5 truncate rounded-md px-2.5 py-1.5 text-left text-xs transition-all"
                  style={{
                    backgroundColor: isSelected ? "rgba(56,189,248,0.18)" : "rgba(255,255,255,0.02)",
                    border: isSelected
                      ? "1px solid var(--accent)"
                      : "1px solid rgba(255,255,255,0.06)",
                    color: isSelected ? "var(--accent)" : "var(--foreground)",
                    boxShadow: isSelected ? "0 0 0 2px rgba(56,189,248,0.15)" : "none",
                  }}
                >
                  <span
                    className="flex h-3 w-3 flex-shrink-0 items-center justify-center rounded-full"
                    style={{
                      border: `1.5px solid ${isSelected ? "var(--accent)" : "var(--muted)"}`,
                    }}
                  >
                    {isSelected && (
                      <span
                        className="h-1.5 w-1.5 rounded-full"
                        style={{ backgroundColor: "var(--accent)" }}
                      />
                    )}
                  </span>
                  <span className="truncate">{formatTickerLabel(it.market, it.symbol)}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
