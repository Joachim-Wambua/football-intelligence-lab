import { useId } from "react";
import type { Pass, Team } from "@/lib/contracts";

/** Rendering guard only: no progression or completion analytics are computed. */
export function hasCoordinates(pass: Pass): boolean {
  return [pass.x, pass.y, pass.end_x, pass.end_y].every(value => value !== null && Number.isFinite(value)) &&
    pass.x! >= 0 && pass.x! <= 120 && pass.end_x! >= 0 && pass.end_x! <= 120 &&
    pass.y! >= 0 && pass.y! <= 80 && pass.end_y! >= 0 && pass.end_y! <= 80;
}
export function PassingPitch({ passes, player }: { passes: Pass[]; player: string }) {
  const uid = useId().replace(/:/g, "");
  const visible = passes.filter(hasCoordinates);
  return <figure>
    <svg viewBox="-5 -5 130 90" role="img" aria-labelledby={`${uid}-title ${uid}-description`} className="w-full rounded-lg" style={{ background: "var(--pitch)" }}>
      <title id={`${uid}-title`}>{player} passing map</title><desc id={`${uid}-description`}>Attacking left to right. Solid arrows show completed passes; dashed arrows show incomplete passes. {visible.length} of {passes.length} recorded passes have drawable coordinates.</desc>
      <defs>{["complete", "incomplete"].map(kind => <marker key={kind} id={`${uid}-${kind}`} viewBox="0 0 6 6" refX="5" refY="3" markerWidth="4" markerHeight="4" orient="auto"><path d="M0 0L6 3L0 6Z" fill={`var(--chart-${kind})`}/></marker>)}</defs>
      <g fill="none" stroke="var(--pitch-line)" strokeWidth=".4"><rect width="120" height="80"/><path d="M60 0V80M0 18H18V62H0M120 18H102V62H120M0 30H6V50H0M120 30H114V50H120"/><circle cx="60" cy="40" r="9.15"/><circle cx="60" cy="40" r=".6"/></g>
      {visible.map((pass, index) => <line key={`${pass.id ?? index}-${index}`} x1={pass.x!} y1={pass.y!} x2={pass.end_x!} y2={pass.end_y!} stroke={`var(--chart-${pass.completed ? "complete" : "incomplete"})`} strokeWidth=".65" strokeDasharray={pass.completed ? undefined : "2 1.5"} markerEnd={`url(#${uid}-${pass.completed ? "complete" : "incomplete"})`} opacity=".85"><title>{pass.completed ? "Completed" : "Incomplete"} pass at minute {pass.minute ?? "unknown"}</title></line>)}
    </svg>
    <figcaption className="mt-4 space-y-2 text-xs text-muted"><p><span style={{ color: "var(--chart-complete)" }}>━━▶ Completed</span><span className="ml-6" style={{ color: "var(--chart-incomplete)" }}>┄┄▶ Incomplete</span></p><p>Attack → · StatsBomb 120 × 80 coordinates. {passes.length - visible.length} passes omitted because coordinates are unavailable or invalid.</p>{!passes.length && <p>No passes recorded for this player.</p>}</figcaption>
  </figure>;
}

export function ShotComparison({ teams }: { teams: Team[] }) {
  // Counts come from the API. Scaling bar widths is presentation only.
  const max = Math.max(1, ...teams.map(team => team.shots));
  return <figure><ul className="space-y-5">{teams.map(team => <li key={team.team_id}><div className="mb-2 flex justify-between gap-2 text-sm"><span className="font-bold">{team.team}</span><span className="text-muted">{team.shots} shots · {team.shot_goals} shot goals</span></div><div aria-hidden="true" className="space-y-1"><div className="h-3 rounded-sm bg-raised" style={{ width: `${team.shots / max * 100}%`, border: "1px solid var(--muted)" }}/><div className="h-3 rounded-sm" style={{ width: `${team.shot_goals / max * 100}%`, background: "var(--chart-complete)", backgroundImage: "repeating-linear-gradient(135deg, transparent, transparent 3px, var(--pitch) 3px, var(--pitch) 4px)" }}/></div></li>)}</ul><figcaption className="mt-5 text-xs text-muted">Upper bar: shots. Lower striped bar: shot goals. Own goals excluded.</figcaption></figure>;
}
