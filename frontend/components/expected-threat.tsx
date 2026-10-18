"use client";
import { useState } from "react";
import useSWR from "swr";
import { apiGet } from "@/lib/api";
import { xtModelSchema, xtPlayersSchema, xtActionsSchema, filterXTActions, formatXT, type XTModel } from "@/lib/xt-contracts";
import { ErrorState, LoadingState, Panel, SelectField } from "./ui";
import { XTHeatmap } from "./xt-heatmap";
const options = { shouldRetryOnError: false, revalidateOnFocus: false };

/** Fetch the frozen model for a selected match/team and present its limitations.
 * Input IDs come from the match dashboard; output is an isolated research panel.
 * Model errors stay local, so existing passing analysis remains usable.
 */
export function ExpectedThreat({ matchId, teamId }: { matchId: number; teamId: number }) {
  const model = useSWR("/xt/model", path => apiGet(path, xtModelSchema), options);
  return <Panel id="expected-threat" title="Expected Threat" subtitle="Experimental, model-based movement value; not per-90 statistics.">
    <p className="mb-5 rounded-lg border border-border bg-raised p-4 text-sm font-bold">Experimental xT — six Leverkusen training matches, two held out; only 26 of 192 zones contain observed shots. Not calibrated or broadly representative. Do not use for definitive scouting assessments.</p>
    {model.error ? <ErrorState message={model.error.message} retry={() => void model.mutate()}/> : !model.data ? <LoadingState label="Loading fitted xT model…"/> : <>
      <p className="mb-4 text-sm text-muted">{model.data.provider} · Trained {model.data.trained_at.slice(0, 10)} · {model.data.coverage.train_ids.length} training / {model.data.coverage.held_out_ids.length} held-out matches · {model.data.coverage.shot_zones}/{model.data.coverage.total_zones} shot-observed zones. <a className="underline" href={model.data.provenance}>Data provenance</a>. Model SHA256: <span className="break-all">{model.data.model_id}</span>.</p>
      <p className="mb-5 text-xs text-muted">{model.data.coverage.training_shots} training shots, {model.data.coverage.training_goals} goals. Coordinates: {model.data.coordinate_system}. Fallback: {model.data.fallback}. Simplified action-conditioned values, not actual possession-goal probabilities.</p>
      <XTMatch key={`${matchId}-${teamId}-${model.data.model_id}`} matchId={matchId} teamId={teamId} model={model.data}/>
    </>}
  </Panel>;
}

/** Present full-match server totals with an opt-in overlay for the same model.
 * ID/hash-keyed mounting resets page state across selections. A model mismatch
 * blocks comparison instead of mixing estimates from different deployments.
 */
function XTMatch({ matchId, teamId, model }: { matchId: number; teamId: number; model: XTModel }) {
  const players = useSWR(`/matches/${matchId}/teams/${teamId}/xt/players`, path => apiGet(path, xtPlayersSchema), options);
  const [overlay, setOverlay] = useState(false);
  return <div className="space-y-6"><label className="flex min-h-11 items-center gap-3 text-sm font-bold"><input type="checkbox" checked={overlay} onChange={e => setOverlay(e.target.checked)}/>Show valued-action overlay and event table</label>
    {overlay ? <XTOverlay matchId={matchId} teamId={teamId} model={model}/> : <XTHeatmap model={model}/>}
    <h3 className="text-lg font-bold">Player xT rankings</h3><p className="text-xs text-muted">Server-ranked by positive xT, net xT and ID. Counts split rated successful passes and observed carries. Full-match totals, independent of overlay pagination.</p>
    {players.error ? <ErrorState message={players.error.message} retry={() => void players.mutate()}/> : !players.data ? <LoadingState label="Loading player xT totals…"/> : players.data.model_id !== model.model_id ? <p role="alert">Model versions differ. Reload before comparing values.</p> : !players.data.players.length ? <p>No identified move-makers for this team.</p> :
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable player xT rankings"><table className="w-full text-sm"><caption className="sr-only">Model-based player xT totals</caption><thead><tr>{["Player", "Positive xT", "Net xT", "Rated / attempts", "Rated passes", "Rated carries"].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{players.data.players.map(row => <tr key={row.player_id}><th scope="row">{row.player}</th><td>{formatXT(row.positive_xt)}</td><td>{formatXT(row.net_xt)}</td><td>{row.rated_action_count}/{row.action_count}</td><td>{row.rated_passes}</td><td>{row.rated_carries}</td></tr>)}</tbody></table></div>}
  </div>;
}

/** Fetch a bounded event page for match/team and render type/sign filters.
 * Filters apply to this page only; full-match totals remain server-owned. Nulls
 * remain in the text alternative, while only rated moves become pitch overlays.
 */
function XTOverlay({ matchId, teamId, model }: { matchId: number; teamId: number; model: XTModel }) {
  const [offset, setOffset] = useState(0);
  const [type, setType] = useState("all"), [sign, setSign] = useState("all");
  const query = useSWR(`/matches/${matchId}/teams/${teamId}/xt/actions?limit=200&offset=${offset}`, path => apiGet(path, xtActionsSchema), options);
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState label="Loading xT action page…"/>;
  if (query.data.model_id !== model.model_id) return <p role="alert">Model versions differ. Reload the workspace.</p>;
  const actions = filterXTActions(query.data.actions, type, sign);
  return <div className="space-y-4"><div className="grid gap-3 sm:grid-cols-2"><SelectField label="xT action type" value={type} onChange={setType}><option value="all">Passes and carries</option><option value="Pass">Passes</option><option value="Carry">Carries</option></SelectField><SelectField label="xT change" value={sign} onChange={setSign}><option value="all">All values (including unrated)</option><option value="positive">Positive xT</option><option value="negative">Negative xT</option></SelectField></div>
    <p role="status" className="text-sm text-muted">Page offset {offset}, {query.data.actions.length} of {query.data.total} attempts loaded. Filters apply to this page: {actions.length} shown. Only rated moves with coordinates appear on the pitch.</p>
    <XTHeatmap model={model} actions={actions}/>
    <div className="flex gap-3"><button className="min-h-10 rounded border border-border px-3 disabled:opacity-50" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 200))}>Previous actions</button><button className="min-h-10 rounded border border-border px-3 disabled:opacity-50" disabled={offset + query.data.actions.length >= query.data.total} onClick={() => setOffset(offset + 200)}>Next actions</button></div>
    <details><summary className="cursor-pointer py-3 font-bold">Valued action details ({actions.length})</summary><div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable xT action details"><table className="w-full text-sm"><caption className="sr-only">xT action page including unrated and missing-coordinate attempts</caption><thead><tr>{["Event", "Player", "Type", "Period / minute", "Start → end", "Outcome", "xT"].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{actions.map(a => <tr key={a.event_index}><td>{a.id ?? a.event_index}</td><td>{a.player ?? "Unknown"}</td><td>{a.type}</td><td>{a.period ?? "?"} / {a.minute ?? "?"}</td><td>({a.x ?? "?"}, {a.y ?? "?"}) → ({a.end_x ?? "?"}, {a.end_y ?? "?"})</td><td>{a.successful ? "Observed successful move" : "Unsuccessful or ineligible"}</td><td>{formatXT(a.xt)}</td></tr>)}</tbody></table></div></details>
  </div>;
}
