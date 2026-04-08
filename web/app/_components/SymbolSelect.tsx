"use client";

// WHY: 리밸런싱 플래너의 테이블 행은 공간이 좁아 full SymbolPicker(칩 그리드)가
//      맞지 않는다. /meta/universe 에서 동일한 시드 종목을 받아 native select 로
//      컴팩트하게 노출하되 다크 테마에 맞춰 스타일링한다.

import { useEffect, useState } from "react";
import { formatTickerLabel } from "./SymbolPicker";

interface UniverseItem {
  symbol: string;
  market: string;
}

interface UniverseMetaResponse {
  by_market: Record<string, UniverseItem[]>;
  markets: string[];
}

let _cache: UniverseMetaResponse | null = null;
let _pending: Promise<UniverseMetaResponse> | null = null;

function loadUniverse(): Promise<UniverseMetaResponse> {
  if (_cache) return Promise.resolve(_cache);
  if (_pending) return _pending;
  _pending = fetch("/api/meta/universe")
    .then((r) => r.json())
    .then((d: UniverseMetaResponse) => {
      _cache = d;
      return d;
    });
  return _pending;
}

interface SymbolSelectProps {
  value: string;
  onChange: (symbol: string) => void;
  placeholder?: string;
}

/**
 * 공용 인라인 심볼 셀렉트. 시장별 optgroup 으로 그룹화.
 */
export default function SymbolSelect({
  value,
  onChange,
  placeholder = "종목 선택",
}: SymbolSelectProps) {
  const [meta, setMeta] = useState<UniverseMetaResponse | null>(null);

  useEffect(() => {
    let alive = true;
    loadUniverse().then((d) => alive && setMeta(d));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded border px-2 py-1 text-xs"
      style={{
        backgroundColor: "var(--card-bg)",
        borderColor: "var(--border)",
        color: "var(--foreground)",
      }}
    >
      <option value="" disabled>
        {placeholder}
      </option>
      {meta &&
        meta.markets.map((m) => (
          <optgroup key={m} label={m}>
            {(meta.by_market[m] ?? []).map((it) => (
              <option key={`${m}:${it.symbol}`} value={it.symbol}>
                {formatTickerLabel(m, it.symbol)}
              </option>
            ))}
          </optgroup>
        ))}
    </select>
  );
}
