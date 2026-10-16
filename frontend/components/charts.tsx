"use client";
import { useId, useState } from "react";
import type { Pass, Team } from "@/lib/contracts";
import { filterPasses, type PassFilter } from "@/lib/pass-filters";
import { SelectField } from "./ui";

/** Rendering guard only: no progression or completion analytics are computed. */
export function hasCoordinates(pass: Pass): boolean {
  return pass.valid_geometry && [pass.x, pass.y, pass.end_x, pass.end_y].every(value => value !== null && Number.isFinite(value)) &&
    pass.x! >= 0 && pass.x! <= 120 && pass.end_x! >= 0 && pass.end_x! <= 120 &&
    pass.y! >= 0 && pass.y! <= 80 && pass.end_y! >= 0 && pass.end_y! <= 80;
}
export function PassingPitch({ passes, player }: { passes: Pass[]; player: string }) {
  const uid = useId().replace(/:/g, "");
  const [filter, setFilter] = useState<PassFilter>("all");
  const [active, setActive] = useState<number | null>(null);
  const filtered = filterPasses(passes, filter);
  const visible = filtered.map((pass, index) => ({ pass, index })).filter(({ pass }) => hasCoordinates(pass));
  const selected = active === null ? null : filtered[active];
  const outcome = (pass: Pass) => !pass.valid_geometry ? "Unclassified (invalid geometry)" : pass.completed_progressive ? "Completed progressive" : pass.progressive ? "Progressive attempt, unsuccessful" : "Not progressive";
  const value = (number: number | null) => number === null ? "Unavailable" : number.toFixed(2);
  const describe = (pass: Pass, index: number) => `Pass ${index + 1}. Period ${pass.period ?? "unknown"}, minute ${pass.minute ?? "unknown"}, second ${pass.second ?? "unknown"}. ${pass.completed ? "Completed" : "Unsuccessful"}. ${outcome(pass)}. Progression ${value(pass.progression_m)} m equivalent.`;
  return <figure>
    <div className="mb-4"><SelectField label="Pass filter" value={filter} onChange={next => { setFilter(next as PassFilter); setActive(null); }}><option value="all">All passes</option><option value="completed">Completed passes</option><option value="unsuccessful">Unsuccessful passes</option><option value="progressive">Progressive passes (all outcomes)</option></SelectField></div>
    <p className="mb-3 text-sm text-muted" role="status">Showing {filtered.length} of {passes.length} passes. Progressive includes unsuccessful geometric attempts.</p>
    <svg viewBox="-5 -5 130 90" role="group" aria-labelledby={`${uid}-title`} aria-describedby={`${uid}-description`} className="w-full rounded-lg" style={{ background: "var(--pitch)" }}>
      <title id={`${uid}-title`}>{player} passing map</title><desc id={`${uid}-description`}>Attacking left to right. Solid arrows show completed passes; dashed arrows show incomplete passes. {visible.length} of {filtered.length} filtered passes have drawable coordinates. Focus or hover an arrow for details; a pass table is available below.</desc>
      <defs>{["complete", "incomplete"].map(kind => <marker key={kind} id={`${uid}-${kind}`} viewBox="0 0 6 6" refX="5" refY="3" markerWidth="4" markerHeight="4" orient="auto"><path d="M0 0L6 3L0 6Z" fill={`var(--chart-${kind})`}/></marker>)}</defs>
      <g fill="none" stroke="var(--pitch-line)" strokeWidth=".4"><rect width="120" height="80"/><path d="M60 0V80M0 18H18V62H0M120 18H102V62H120M0 30H6V50H0M120 30H114V50H120"/><circle cx="60" cy="40" r="9.15"/><circle cx="60" cy="40" r=".6"/></g>
      {visible.map(({ pass, index }) => <g key={`${pass.id ?? index}-${index}`} role="button" tabIndex={0} aria-label={describe(pass, index)} aria-pressed={active === index}
        onMouseEnter={() => setActive(index)} onFocus={() => setActive(index)} onClick={() => setActive(index)}
        onKeyDown={event => { if (event.key === "Escape") setActive(null); if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setActive(index); } }}>
        <title>{describe(pass, index)}</title>
        <line x1={pass.x!} y1={pass.y!} x2={pass.end_x!} y2={pass.end_y!} stroke="transparent" strokeWidth="4"/>
        <line data-pass="true" x1={pass.x!} y1={pass.y!} x2={pass.end_x!} y2={pass.end_y!} stroke={`var(--chart-${pass.completed ? "complete" : "incomplete"})`} strokeWidth={active === index ? "1.2" : ".65"} strokeDasharray={pass.completed ? undefined : "2 1.5"} markerEnd={`url(#${uid}-${pass.completed ? "complete" : "incomplete"})`} opacity=".85"/>
      </g>)}
    </svg>
    <figcaption className="mt-4 space-y-2 text-xs text-muted"><p><span style={{ color: "var(--chart-complete)" }}>━━▶ Completed</span><span className="ml-6" style={{ color: "var(--chart-incomplete)" }}>┄┄▶ Incomplete</span></p><p>Attack → · StatsBomb 120 × 80 coordinates. {filtered.length - visible.length} passes omitted because coordinates are unavailable or invalid.</p>{!passes.length ? <p>No passes recorded for this player.</p> : !filtered.length && <p>No passes match this filter.</p>}</figcaption>
    <div className="my-4 rounded-lg border border-border bg-raised p-4 text-sm" role="status" aria-live="polite">
      {selected ? <><p>{describe(selected, active!)}</p><p className="mt-2 text-muted">Start ({selected.x ?? "?"}, {selected.y ?? "?"}) → End ({selected.end_x ?? "?"}, {selected.end_y ?? "?"}). Distance to goal: {value(selected.start_distance_m)} → {value(selected.end_distance_m)} m equivalent.</p><button className="mt-3 min-h-10 rounded border border-border px-3" onClick={() => setActive(null)}>Clear pass details</button></> : "Hover, focus or select a pass to inspect its details."}
    </div>
    <details className="mt-4"><summary className="cursor-pointer py-3 font-bold">Accessible pass details table ({filtered.length})</summary>
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable pass details"><table className="w-full text-sm"><caption className="sr-only">Filtered pass events, including those missing map coordinates</caption><thead><tr>{["Pass", "Period / clock", "Outcome", "Progressive classification", "Start → end", "Progression (m equivalent)"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{filtered.map((pass, index) => <tr key={`${pass.id ?? index}-${index}`}><th scope="row"><button className="min-h-10 rounded border border-border px-3" onClick={() => setActive(index)}>Inspect pass {index + 1}</button></th><td>{pass.period ?? "?"} / {pass.minute ?? "?"}:{pass.second === null || pass.second === undefined ? "??" : String(pass.second).padStart(2, "0")}</td><td>{pass.completed ? "Completed" : "Unsuccessful"}</td><td>{outcome(pass)}</td><td>({pass.x ?? "?"}, {pass.y ?? "?"}) → ({pass.end_x ?? "?"}, {pass.end_y ?? "?"})</td><td>{value(pass.progression_m)}</td></tr>)}</tbody></table></div>
    </details>
  </figure>;
}

export function ShotComparison({ teams }: { teams: Team[] }) {
  // Counts come from the API. Scaling bar widths is presentation only.
  const max = Math.max(1, ...teams.map(team => team.shots));
  return <figure><ul className="space-y-5">{teams.map(team => <li key={team.team_id}><div className="mb-2 flex justify-between gap-2 text-sm"><span className="font-bold">{team.team}</span><span className="text-muted">{team.shots} shots · {team.shot_goals} shot goals</span></div><div aria-hidden="true" className="space-y-1"><div className="h-3 rounded-sm bg-raised" style={{ width: `${team.shots / max * 100}%`, border: "1px solid var(--muted)" }}/><div className="h-3 rounded-sm" style={{ width: `${team.shot_goals / max * 100}%`, background: "var(--chart-complete)", backgroundImage: "repeating-linear-gradient(135deg, transparent, transparent 3px, var(--pitch) 3px, var(--pitch) 4px)" }}/></div></li>)}</ul><figcaption className="mt-5 text-xs text-muted">Upper bar: shots. Lower striped bar: shot goals. Own goals excluded.</figcaption></figure>;
}
