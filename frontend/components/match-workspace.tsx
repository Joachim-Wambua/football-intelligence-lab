"use client";
import { useState } from "react";
import useSWR from "swr";
import { z } from "zod";
import { apiGet } from "@/lib/api";
import { shotSchema, insightsSchema, type Shot } from "@/lib/contracts";
import { Panel, LoadingState, ErrorState, SelectField } from "./ui";

const options = { shouldRetryOnError: false, revalidateOnFocus: false, keepPreviousData: false };

/** Keys include match/team; remounting also clears player filters and event focus. */
export function MatchWorkspace({ matchId, teamId }: { matchId: number; teamId: number }) {
  return <><ShotSection key={`${matchId}-${teamId}`} matchId={matchId} teamId={teamId}/><Insights key={`insights-${matchId}-${teamId}`} matchId={matchId} teamId={teamId}/></>;
}
function ShotSection({ matchId, teamId }: { matchId: number; teamId: number }) {
  const query = useSWR(`/matches/${matchId}/shots?team_id=${teamId}`, path => apiGet(path, z.array(shotSchema)), options);
  return <Panel id="shots" title="Shot map" subtitle="Selected team · StatsBomb 120 × 80 · attacking right in every period">
    {query.error ? <ErrorState message={query.error.message} retry={() => void query.mutate()}/> : !query.data ? <LoadingState label="Loading shot events…"/> : <ShotMap shots={query.data}/>}
  </Panel>;
}
const description = (shot: Shot) => `${shot.player ?? "Unknown player"} · Period ${shot.period ?? "unknown"}, minute ${shot.minute ?? "unknown"} · ${shot.goal ? "Goal" : "Other shot"} · xG ${shot.xg ?? "unavailable"} · location ${shot.x ?? "unknown"}, ${shot.y ?? "unknown"}`;

/** SVG uses provider units directly: (60,40) is the pitch centre. No reflection.
 * Marker radius is a display encoding only: r² = 4 + 32*xG gives area linear
 * in provider xG plus a visible baseline. Missing xG has baseline size and text.
 * Invalid locations remain in the event table; they never become (0,0).
 */
export function ShotMap({ shots }: { shots: Shot[] }) {
  const [player, setPlayer] = useState("");
  const [selected, setSelected] = useState<Shot>();
  const players = [...new Map(shots.filter(s => s.player_id != null).map(s => [s.player_id, s.player ?? `Player ${s.player_id}`])).entries()];
  const filtered = shots.filter(s => !player || String(s.player_id) === player);
  const plotted = filtered.filter(s => s.x !== null && s.y !== null);
  return <div className="space-y-4">
    <SelectField label="Shot player" value={player} onChange={value => { setPlayer(value); setSelected(undefined); }}><option value="">All players</option>{players.map(([id, name]) => <option key={id} value={id!}>{name}</option>)}</SelectField>
    <p className="text-sm text-muted">Goals: square with G. Other shots: circle. Marker area increases with provider xG; unavailable xG uses baseline size. {filtered.length - plotted.length} shots omitted for missing location. All recorded periods included, including shootouts.</p>
    {!filtered.length && <p role="status">No shots for this selection.</p>}
    <svg viewBox="-5 -5 130 90" className="w-full rounded border border-border bg-raised" aria-label="Interactive shot map, attacking right" role="group">
      <g fill="none" stroke="currentColor" strokeWidth=".4" aria-hidden="true"><rect width="120" height="80"/><path d="M60 0V80 M0 18H18V62H0 M120 18H102V62H120"/><circle cx="60" cy="40" r="9.15"/></g>
      {plotted.map(shot => { const radius = Math.sqrt(4 + 32 * (shot.xg ?? 0)); return <g key={shot.event_index} role="button" tabIndex={0} aria-label={description(shot)} onFocus={() => setSelected(shot)} onMouseEnter={() => setSelected(shot)} onClick={() => setSelected(shot)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(shot); } if (event.key === "Escape") setSelected(undefined); }} className="cursor-pointer text-accent focus:outline focus:outline-2">
        <circle cx={shot.x!} cy={shot.y!} r={Math.max(4, radius)} fill="transparent"/>
        {shot.goal ? <><rect x={shot.x! - radius} y={shot.y! - radius} width={radius * 2} height={radius * 2} fill="currentColor"/><text x={shot.x!} y={shot.y! + 1} textAnchor="middle" fontSize="3" className="fill-accent-foreground">G</text></> : <circle cx={shot.x!} cy={shot.y!} r={radius} fill="none" stroke="currentColor" strokeWidth=".8"/>}
      </g>; })}
    </svg>
    <p role="status" aria-live="polite">{selected ? description(selected) : "Focus or select a shot to inspect its details."}</p>
    {selected && <button className="min-h-11 underline" onClick={() => setSelected(undefined)}>Clear shot details</button>}
    <details><summary className="min-h-11 cursor-pointer">All filtered shot events ({filtered.length})</summary><ul>{filtered.map(shot => <li key={shot.event_index}><button className="min-h-11 text-left underline" onClick={() => setSelected(shot)}>{description(shot)}</button></li>)}</ul></details>
  </div>;
}
function Insights({ matchId, teamId }: { matchId: number; teamId: number }) {
  const query = useSWR(`/matches/${matchId}/teams/${teamId}/insights`, path => apiGet(path, insightsSchema), options);
  return <Panel id="insights" title="Match insights" subtitle="Verifiable evidence from Python; counts and model estimates are labelled separately.">
    {query.error ? <ErrorState message={query.error.message} retry={() => void query.mutate()}/> : !query.data ? <LoadingState label="Loading match insights…"/> : <><ul className="space-y-4">{query.data.observations.map(row => <li key={row.metric}><h3 className="font-bold">{row.metric.replaceAll("_", " ")}: {row.player && `${row.player} · `}{row.value ?? "Unavailable"}{row.denominator !== null && ` / ${row.denominator}`}</h3><p className="text-sm text-muted">{row.definition}</p>{row.model_id && <p className="text-xs">Model: {row.model_id}</p>}</li>)}</ul>{query.data.xt_status === "unavailable" && <p role="status">Experimental xT unavailable. Observed evidence remains available.</p>}</>}
  </Panel>;
}
