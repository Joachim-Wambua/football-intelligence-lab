"use client";

import { useState, type FormEvent } from "react";
import useSWR from "swr";
import { z } from "zod";
import { apiGet } from "@/lib/api";
import { teamProgressionSchema, passSchema, type Player } from "@/lib/contracts";
import { ErrorState, LoadingState, Panel, SelectField } from "./ui";
import { PassingPitch } from "./charts";

const options = { shouldRetryOnError: false, revalidateOnFocus: false };

export function ProgressivePassing({ matchId, teamId, players, player, onSelectPlayer }: {
  matchId: number; teamId: number; players: Player[]; player: Player;
  onSelectPlayer: (id: number) => void;
}) {
  // No JS default for the metric: the initial request uses Python's default.
  const [threshold, setThreshold] = useState<number>();
  const [validationError, setValidationError] = useState("");
  const suffix = threshold === undefined ? "" : `?threshold_m=${threshold}`;
  const query = useSWR(`/matches/${matchId}/teams/${teamId}/progressive-passing${suffix}`, path => apiGet(path, teamProgressionSchema), options);
  function applyThreshold(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = Number(new FormData(event.currentTarget).get("threshold"));
    if (!Number.isFinite(value) || value <= 0) { setValidationError("Enter a finite positive threshold."); return; }
    setValidationError("");
    setThreshold(value);
  }
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState label="Loading progressive passing rankings…"/>;
  const { definition, players: ranking } = query.data;
  return <>
    <Panel title="Progressive passing rankings" subtitle="Ranked by completed progressive passes, then geometric attempts, then player ID.">
      <form onSubmit={applyThreshold} className="mb-5 flex flex-wrap items-end gap-3">
        <label className="text-sm font-bold">Minimum distance reduction (m equivalent)<input key={definition.threshold_m} name="threshold" type="number" min="0.01" step="any" required defaultValue={definition.threshold_m} className="mt-2 block w-48 rounded-lg border border-border bg-surface p-3 text-foreground"/></label>
        <button className="min-h-12 rounded-lg bg-accent px-4 font-bold text-accent-foreground" type="submit">Apply threshold</button>
      </form>
      {validationError && <p role="alert">{validationError}</p>}
      <p className="mb-4 text-sm text-muted">Progressive: at least {definition.threshold_m} m-equivalent closer to goal ({definition.goal_x}, {definition.goal_y}), assuming a {definition.pitch_length_m} × {definition.pitch_width_m} m pitch. Geometric attempts include unsuccessful passes. Completed progressive requires both flags.</p>
      {ranking.length ? <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable progressive passing rankings"><table className="w-full text-sm"><caption className="sr-only">Progressive passing rankings for the selected team</caption><thead><tr>{["Rank", "Player", "Passes", "Valid geometry", "Progressive attempts", "Completed progressive", "Progressive %", "Net progression (m equivalent)"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{ranking.map(row => <tr key={row.player_id}><td>{row.rank}</td><th scope="row"><button className="min-h-10 text-left underline" onClick={() => onSelectPlayer(row.player_id)}>{row.player}</button></th><td>{row.passes}</td><td>{row.valid_geometry}/{row.passes}</td><td>{row.progressive_attempts}</td><td>{row.completed_progressive}</td><td>{row.progressive_pct.toFixed(1)}%</td><td>{row.net_progression_m?.toFixed(2) ?? "Unavailable"}</td></tr>)}</tbody></table></div> : <p>No named passers available for this team.</p>}
      <p className="mt-4 text-xs text-muted">Rate denominator: all attempts, including unclassifiable geometry. Net progression includes negative reductions and both outcomes. Counts are not per 90 minutes.</p>
    </Panel>
    <Panel id="passes" title="Passing intelligence" subtitle="Explore Python-classified passes; focus an arrow or use its table for details.">
      <SelectField label="Player" value={player.player_id} onChange={value => onSelectPlayer(Number(value))}>{players.map(item => <option key={item.player_id} value={item.player_id}>{item.player}</option>)}</SelectField>
      <div className="mt-5"><PlayerPasses key={`${player.player_id}-${definition.threshold_m}`} matchId={matchId} player={player} threshold={definition.threshold_m}/></div>
    </Panel>
  </>;
}

function PlayerPasses({ matchId, player, threshold }: { matchId: number; player: Player; threshold: number }) {
  const query = useSWR(`/matches/${matchId}/players/${player.player_id}/passes?threshold_m=${threshold}`, path => apiGet(path, z.array(passSchema)), options);
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState label="Loading player passes…"/>;
  return <PassingPitch passes={query.data} player={player.player}/>;
}
