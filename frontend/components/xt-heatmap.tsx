"use client";
import { useId, useState } from "react";
import { formatXT, type XTAction, type XTModel } from "@/lib/xt-contracts";

/** Render an API-owned ny-by-nx surface plus optional valued actions as SVG/text.
 * Inputs use normalized StatsBomb coordinates. Null-valued or missing-coordinate
 * actions have no overlay; the full surface remains inspectable. Color scaling
 * changes presentation only, never the supplied zone values or their certainty.
 */
export function XTHeatmap({ model, actions = [] }: { model: XTModel; actions?: XTAction[] }) {
  const uid = useId();
  const [selected, setSelected] = useState<{ row: number; col: number } | null>(null);
  const width = 120 / model.nx, height = 80 / model.ny;
  const max = Math.max(...model.surface.flat(), Number.EPSILON);
  const label = (r: number, c: number) => `Zone row ${r + 1}, column ${c + 1}: xT ${model.surface[r][c].toFixed(6)}; ${model.shot_counts[r][c]} observed shots.`;
  const drawable = actions.filter(a => a.xt !== null && [a.x, a.y, a.end_x, a.end_y].every(v => v !== null && Number.isFinite(v)));
  return <figure>
    <svg role="group" aria-labelledby={`${uid}-title`} aria-describedby={`${uid}-description`} viewBox="-2 -2 124 84" className="w-full rounded-lg">
      <title id={`${uid}-title`}>Fitted experimental xT surface</title><desc id={`${uid}-description`}>{model.nx} columns by {model.ny} rows, attacking right. Focus or hover zones; numeric values and shot support are also in the table below.</desc>
      {model.surface.flatMap((row, r) => row.map((value, c) => <rect key={`${r}-${c}`} data-zone="true" x={c * width} y={r * height} width={width} height={height}
        fill={`color-mix(in srgb, var(--xt-high) ${value / max * 100}%, var(--xt-low))`} stroke="var(--pitch-line)" strokeWidth=".15"
        role="button" tabIndex={0} aria-label={label(r, c)} aria-pressed={selected?.row === r && selected.col === c}
        onMouseEnter={() => setSelected({ row: r, col: c })} onFocus={() => setSelected({ row: r, col: c })} onClick={() => setSelected({ row: r, col: c })}
        onKeyDown={e => { if (e.key === "Escape") setSelected(null); if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected({ row: r, col: c }); } }}><title>{label(r, c)}</title></rect>))}
      <g fill="none" stroke="var(--pitch-line)" strokeWidth=".4" pointerEvents="none"><rect width="120" height="80"/><path d="M60 0V80M0 18H18V62H0M120 18H102V62H120"/><circle cx="60" cy="40" r="9.15"/></g>
      {drawable.map(a => <g key={a.event_index} role="img" aria-label={`${a.type}, ${a.player ?? "unknown player"}, xT ${formatXT(a.xt)}`}><title>{a.type}: {a.player ?? "Unknown"}, minute {a.minute ?? "?"}, xT {formatXT(a.xt)}</title><line data-xt-action="true" x1={a.x!} y1={a.y!} x2={a.end_x!} y2={a.end_y!} stroke={a.xt! < 0 ? "var(--negative)" : "var(--positive)"} strokeWidth=".85" strokeDasharray={a.type === "Carry" ? "2 1" : undefined}/><circle cx={a.end_x!} cy={a.end_y!} r=".8" fill="var(--foreground)"/></g>)}
    </svg>
    <figcaption className="mt-3 space-y-2 text-sm text-muted"><p>Attack →. Low to high xT: <span aria-hidden="true" className="inline-block h-3 w-28 rounded" style={{ background: "linear-gradient(to right,var(--xt-low),var(--xt-high))" }}/>. Color encodes fitted values, not certainty.</p><p>Overlay: solid passes, dashed carries; dots mark destinations. Signed values are in the action table. Zero is defined; null is unrated.</p></figcaption>
    <p className="my-4 rounded-lg bg-raised p-4 text-sm" role="status" aria-live="polite">{selected ? label(selected.row, selected.col) : "Hover or focus a zone to inspect its value."}</p>
    <details><summary className="cursor-pointer py-3 font-bold">Zone values and observed shot support</summary><div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable xT zone values"><table className="w-full text-sm"><caption className="sr-only">All fitted xT zones, rows top to bottom and columns left to right</caption><thead><tr><th scope="col">Row</th><th scope="col">Column</th><th scope="col">Fitted xT</th><th scope="col">Observed shots</th></tr></thead><tbody>{model.surface.flatMap((row, r) => row.map((v, c) => <tr key={`${r}-${c}`}><td>{r + 1}</td><td>{c + 1}</td><td>{v.toFixed(6)}</td><td>{model.shot_counts[r][c]}</td></tr>))}</tbody></table></div></details>
  </figure>;
}
