"use client";

// WHY: 백테스트/리밸런싱 입력 변수들의 의미/단위/기본값이 UI 에서 파편적으로
//      노출되어 사용자가 값을 이해하기 어려웠다. /meta/backtest-params 를 한 번
//      조회해 모든 변수 설명을 단일 카드로 보여주는 범용 설명 블록을 제공한다.

import { useEffect, useState } from "react";

interface ParamMeta {
  key: string;
  label: string;
  description: string;
  type: string;
  unit?: string;
  default: unknown;
  options?: string[];
}

interface ParamsResponse {
  params: ParamMeta[];
}

/**
 * 변수 설명 아코디언.
 *
 * @param keys 노출할 키 목록. 비우면 전체 표시. 리밸런싱 페이지는 일부만 표시.
 */
export default function ParamHelp({ keys }: { keys?: string[] }) {
  const [params, setParams] = useState<ParamMeta[]>([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetch("/api/meta/backtest-params")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d: ParamsResponse) => {
        if (!alive) return;
        const filtered = keys ? d.params.filter((p) => keys.includes(p.key)) : d.params;
        setParams(filtered);
      })
      .catch((e) => alive && setError(String(e)));
    return () => {
      alive = false;
    };
  }, [keys]);

  if (error) {
    return (
      <p className="text-xs" style={{ color: "var(--danger)" }}>
        변수 설명 로드 실패: {error}
      </p>
    );
  }

  return (
    <div
      className="rounded border"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--card-bg)" }}
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2 text-sm font-medium"
        style={{ color: "var(--foreground)" }}
      >
        <span>변수 설명 ({params.length}개)</span>
        <span style={{ color: "var(--muted)" }}>{open ? "▲ 접기" : "▼ 펼치기"}</span>
      </button>
      {open && (
        <div className="border-t px-4 py-3" style={{ borderColor: "var(--border)" }}>
          <dl className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {params.map((p) => (
              <div key={p.key} className="flex flex-col gap-0.5">
                <dt className="flex items-baseline gap-2 text-sm font-semibold" style={{ color: "var(--foreground)" }}>
                  {p.label}
                  <span className="font-mono text-xs" style={{ color: "var(--muted)" }}>
                    ({p.key})
                  </span>
                </dt>
                <dd className="text-xs leading-snug" style={{ color: "var(--muted)" }}>
                  {p.description}
                </dd>
                <dd className="text-xs font-mono" style={{ color: "var(--accent)" }}>
                  기본값: {String(p.default ?? "—")}
                  {p.unit && <span className="ml-2" style={{ color: "var(--muted)" }}>[{p.unit}]</span>}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}
