"use client";
import { useState } from "react";
import useSWR from "swr";
import { z } from "zod";
import { apiGet } from "@/lib/api";
import { competitionSchema, matchSchema, summarySchema, type Competition, type Match, type Team } from "@/lib/contracts";
import { collectionQuery, hasPlayerContext, playerCatalogueSchema, playerProfileSchema, type PlayerCollection, type PlayerProfile } from "@/lib/player-contracts";
import { PlayerComparison } from "./player-comparison";
import { ErrorState, LoadingState, Panel, SelectField, MetricCard } from "./ui";
const options = { shouldRetryOnError: false, revalidateOnFocus: false, keepPreviousData: false };

export function PlayerIntelligence() {
  const query = useSWR("/competitions", path => apiGet(path, z.array(competitionSchema)), options);
  const [selected, setSelected] = useState("");
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState label="Loading player datasets…"/>;
  if (!query.data.length) return <Panel title="No datasets">No competitions available.</Panel>;
  const competition = query.data.find(row => `${row.competition_id}:${row.season_id}` === selected) ?? query.data.find(row => row.competition_id === 9 && row.season_id === 281) ?? query.data[0];
  return <div className="mx-auto max-w-6xl space-y-6">
    <header><h1 className="text-3xl font-bold">Player Intelligence</h1><p className="mt-3 text-muted">Recorded contributions, verified playing time and transparent selected-match samples.</p><a className="inline-block min-h-11 py-3 underline" href="/">Match Intelligence workspace</a></header>
    <Panel title="Choose the evidence sample"><SelectField label="Player competition and season" value={`${competition.competition_id}:${competition.season_id}`} onChange={setSelected}>{query.data.map(row => <option key={`${row.competition_id}:${row.season_id}`} value={`${row.competition_id}:${row.season_id}`}>{row.competition_name} · {row.season_name} · {row.competition_gender}</option>)}</SelectField></Panel>
    <CollectionMatches key={`${competition.competition_id}:${competition.season_id}`} competition={competition}/>
    <footer className="text-xs text-muted">Data: <a className="underline" href="https://github.com/statsbomb/open-data">StatsBomb Open Data</a> via the shared Python analytics API. Partial Leverkusen coverage is not a full Bundesliga season. No percentile radar, ratings or physical attributes are inferred.</footer>
  </div>;
}
function CollectionMatches({ competition }: { competition: Competition }) {
  const query = useSWR(`/matches?competition_id=${competition.competition_id}&season_id=${competition.season_id}`, path => apiGet(path, z.array(matchSchema)), options);
  const [selected, setSelected] = useState<number>();
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState label="Loading collection fixtures…"/>;
  if (!query.data.length) return <Panel title="No fixtures">Choose another competition-season.</Panel>;
  const match = query.data.find(row => row.match_id === selected) ?? query.data[0];
  return <><SelectField label="Anchor match for team selection" value={match.match_id} onChange={value => setSelected(Number(value))}>{query.data.map(row => <option key={row.match_id} value={row.match_id}>{row.match_date} · {row.home_team} vs {row.away_team}</option>)}</SelectField><CollectionTeam key={match.match_id} competition={competition} matches={query.data} anchor={match}/></>;
}
function CollectionTeam({ competition, matches, anchor }: { competition: Competition; matches: Match[]; anchor: Match }) {
  const query = useSWR(`/matches/${anchor.match_id}/summary`, path => apiGet(path, summarySchema), options);
  const [selected, setSelected] = useState<number>();
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState label="Loading team identities…"/>;
  if (!query.data.teams.length) return <Panel title="No teams">No team identities recorded.</Panel>;
  const team = query.data.teams.find(row => row.team_id === selected) ?? query.data.teams[0];
  return <><SelectField label="Player team" value={team.team_id} onChange={value => setSelected(Number(value))}>{query.data.teams.map(row => <option key={row.team_id} value={row.team_id}>{row.team}</option>)}</SelectField><CollectionPicker key={team.team_id} competition={competition} matches={matches} anchor={anchor} team={team}/></>;
}
function CollectionPicker({ competition, matches, anchor, team }: { competition: Competition; matches: Match[]; anchor: Match; team: Team }) {
  const [chosen, setChosen] = useState([anchor.match_id]);
  const [applied, setApplied] = useState([anchor.match_id]);
  const candidates = matches.filter(row => row.home_team === team.team || row.away_team === team.team);
  const context = { competitionId: competition.competition_id, seasonId: competition.season_id, teamId: team.team_id, matchIds: applied };
  return <><Panel title="Selected match collection" subtitle="Select one to five fixtures, then apply. Team membership is verified by provider ID in Python.">
    <fieldset className="max-h-64 space-y-2 overflow-y-auto"><legend className="mb-3 text-sm font-bold">Available fixtures involving {team.team}</legend>{candidates.map(row => <label key={row.match_id} className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={chosen.includes(row.match_id)} disabled={!chosen.includes(row.match_id) && chosen.length >= 5} onChange={event => setChosen(event.target.checked ? [...chosen, row.match_id] : chosen.filter(id => id !== row.match_id))}/>{row.match_date} · {row.home_team} vs {row.away_team} · ID {row.match_id}</label>)}</fieldset>
    <p className="my-3 text-sm text-muted">{chosen.length}/5 selected. Applied match IDs: {applied.join(", ")}. Changing checkboxes does not change the displayed evidence until applied.</p>
    <button disabled={!chosen.length} className="min-h-11 rounded-lg bg-accent px-4 font-bold text-accent-foreground disabled:opacity-50" onClick={() => setApplied([...chosen])}>Apply match collection</button>
  </Panel><PlayerCatalogue key={collectionQuery(context)} context={context}/></>;
}

/** Catalogue and profile keys include every context ID; selection/search resets
 * between collections, and delayed responses cannot populate a different player.
 */
export function PlayerCatalogue({ context }: { context: PlayerCollection }) {
  return <PlayerCatalogueContent key={collectionQuery(context)} context={context}/>;
}
function PlayerCatalogueContent({ context }: { context: PlayerCollection }) {
  const path = `/player-intelligence/players?${collectionQuery(context)}`;
  const query = useSWR(path, path => apiGet(path, playerCatalogueSchema), options);
  const [search, setSearch] = useState(""), [selected, setSelected] = useState<number>();
  const [mode, setMode] = useState<"profile" | "comparison">("profile");
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState label="Preparing bounded player collection…"/>;
  if (!hasPlayerContext(query.data.context, context)) return <p role="alert">Player response does not match the selected collection.</p>;
  const filtered = query.data.players.filter(row => `${row.player} ${row.aliases.join(" ")} ${row.player_id}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const player = filtered.find(row => row.player_id === selected) ?? filtered[0];
  return <div className="space-y-6"><div className="flex flex-wrap gap-3" role="group" aria-label="Player workspace view">
    <button className="min-h-11 rounded border border-border px-4" aria-pressed={mode === "profile"} onClick={() => setMode("profile")}>Player profile</button>
    <button className="min-h-11 rounded border border-border px-4" aria-pressed={mode === "comparison"} onClick={() => setMode("comparison")}>Compare players</button>
  </div>{mode === "comparison" ? <PlayerComparison key={path} catalogue={query.data}/> : <><Panel title="Player catalogue" subtitle={query.data.context.sample_label}>
    <label className="mb-2 block font-bold" htmlFor="player-search">Search player name or provider ID</label><input id="player-search" type="search" value={search} onChange={event => setSearch(event.target.value)} className="mb-4 min-h-11 w-full rounded border border-border bg-surface p-3"/>
    {!filtered.length ? <p role="status">No players match this selection.</p> : <SelectField label="Player identity" value={player.player_id} onChange={value => setSelected(Number(value))}>{filtered.map(row => <option key={row.player_id} value={row.player_id}>{row.player} · ID {row.player_id}</option>)}</SelectField>}
  </Panel>{player && <SelectedPlayer key={`${path}-${player.player_id}`} context={context} playerId={player.player_id}/>}</>}</div>;
}
function SelectedPlayer({ context, playerId }: { context: PlayerCollection; playerId: number }) {
  const path = `/player-intelligence/players/${playerId}?${collectionQuery(context)}`;
  const query = useSWR(path, path => apiGet(path, playerProfileSchema), options);
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState label="Loading player contributions…"/>;
  if (query.data.identity.player_id !== playerId || !hasPlayerContext(query.data.context, context)) return <p role="alert">Player response does not match the selected identity.</p>;
  return <PlayerProfileView profile={query.data}/>;
}
const display = (value: number | null | undefined, decimals = 2) => value == null ? "Unavailable" : value.toFixed(decimals);
export function PlayerProfileView({ profile }: { profile: PlayerProfile }) {
  const { identity, context, model } = profile;
  const aggregate = identity.aggregate, stats = aggregate.statistics;
  return <div className="space-y-6">
    <Panel title={identity.player} subtitle={`Provider ID ${identity.player_id} · ${identity.team} · ${identity.positions.join(", ") || "Position unavailable"}`}>
      <p className="mb-3 text-sm">{context.sample_label}. Included match IDs: {context.included_match_ids.join(", ")}. {context.included_match_ids.length} included / {context.requested_match_ids.length} selected; catalogue contains {context.available_catalogue_matches} available fixtures.</p>
      {!!context.failed_matches.length && <p role="status">Excluded matches: {context.failed_matches.map(row => `${row.match_id}: ${row.status}`).join("; ")}. Aggregate per-90 unavailable.</p>}
      {!!context.lineups_unavailable_match_ids.length && <p>Lineups unavailable: {context.lineups_unavailable_match_ids.join(", ")}.</p>}
      <div className="mt-4 grid gap-3 sm:grid-cols-3"><MetricCard label="Confirmed appearances" value={aggregate.appearances} detail={`${aggregate.unknown_appearances} unknown appearances`}/><MetricCard label="Verified total minutes" value={display(aggregate.minutes)} detail={`${display(aggregate.known_minutes)} known elapsed pitch minutes; added time included`}/><MetricCard label="Minutes coverage" value={`${aggregate.minutes_covered_matches} / ${profile.matches.length}`} detail="Included player-match records with reliable minutes"/></div>
      <p className="mt-4 text-sm text-muted">Per-90 requires complete valid positive elapsed minutes for the same numerator matches. Unknown minutes never become zero; known minutes can be a partial sum. Temporary off/on spells are unsupported.</p>
    </Panel>
    <Panel title="Selected-collection contributions" subtitle="Observed events and separately labelled model estimates; no rankings or percentiles.">
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Player aggregate statistics"><table className="w-full text-sm"><caption className="sr-only">Selected collection totals and qualified per-90 values</caption><thead><tr><th scope="col">Metric</th><th scope="col">Total</th><th scope="col">Per 90 elapsed minutes</th></tr></thead><tbody>{[["passes", "Pass attempts"], ["completed_passes", "Completed passes"], ["completed_progressive_passes", "Completed progressive passes"], ["shots", "Shots"], ["goals", "Shot goals"], ["xg", "Provider xG estimate"], ["successful_dribbles", "Successful dribbles"], ["successful_interceptions", "Successful interceptions"], ["xt_positive", "Experimental positive xT estimate"], ["xt_net", "Experimental net xT estimate"]].map(([key, label]) => <tr key={key}><th scope="row">{label}</th><td>{display(stats[key as keyof typeof stats], key.startsWith("xt_") ? 4 : key === "xg" ? 2 : 0)}</td><td>{display(aggregate.per90[key as keyof typeof aggregate.per90])}</td></tr>)}</tbody></table></div>
      <p className="mt-4 text-sm">Provider xG coverage: {stats.shots_with_xg} / {stats.shots} shots. Valid passing geometry: {stats.progressive_valid_geometry} / {stats.passes} attempts. Experimental xT coverage: {stats.xt_rated_actions} / {stats.xt_attempted_actions} moves rated.</p>
      <p className="mt-2 text-sm text-muted">Per-90 match IDs: {aggregate.per90_match_ids.join(", ") || "Unavailable"}. Partial xG coverage suppresses xG per-90. xT totals cover rated moves only.</p>
    </Panel>
    <Panel title="Match-by-match contributions" subtitle="Minutes status and source are inspectable for every included match.">
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Player match contributions"><table className="w-full text-sm"><caption className="sr-only">Player match contribution statistics and minutes provenance</caption><thead><tr>{["Match", "Appearance", "Minutes / status", "Passes completed / attempted", "Completed progressive", "Shots / goals", "xG / coverage", "Dribbles / interceptions", "Experimental net xT / coverage"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{profile.matches.map(row => <tr key={row.match_id}><th scope="row"><a className="underline" href={`/?competition_id=${context.competition_id}&season_id=${context.season_id}&match_id=${row.match_id}&team_id=${context.team_id}`}>{row.match_date} · {row.home_team} vs {row.away_team}</a><p className="normal-case">{row.positions.join(", ") || "Position unavailable"}</p></th><td>{row.appeared === null ? "Unknown" : row.appeared ? "Appeared" : "Did not appear"}</td><td>{display(row.minutes)} · {row.minutes_status.replaceAll("_", " ")}</td><td>{row.statistics.completed_passes} / {row.statistics.passes}</td><td>{row.statistics.completed_progressive_passes}</td><td>{row.statistics.shots} / {row.statistics.goals}</td><td>{display(row.statistics.xg)} / {row.statistics.shots_with_xg} of {row.statistics.shots} shots</td><td>{row.statistics.successful_dribbles} / {row.statistics.successful_interceptions}</td><td>{display(row.statistics.xt_net, 4)} / {row.statistics.xt_rated_actions} of {row.statistics.xt_attempted_actions}</td></tr>)}</tbody></table></div>
      {profile.matches.map(row => <details key={row.match_id} className="mt-3 text-sm"><summary className="min-h-11 cursor-pointer">Minutes and position evidence · Match {row.match_id}</summary><p>{row.minutes_provenance}</p><p>Status: {row.minutes_status.replaceAll("_", " ")}. Model ID: {row.model_id ?? "Unavailable"}.</p><pre className="mt-2 overflow-x-auto whitespace-pre-wrap">{JSON.stringify(row.position_history, null, 2)}</pre></details>)}
    </Panel>
    <Panel title="Definitions, provenance and limitations"><p className="mb-3 font-bold">{model.limitations}</p><p className="mb-3 break-all text-xs">xT {model.status} · Model ID: {model.model_id ?? "Unavailable"} · {model.training_matches ?? "Unknown"} training / {model.held_out_matches ?? "Unknown"} held out · {model.shot_zones ?? "Unknown"}/{model.total_zones ?? "Unknown"} shot-observed zones.</p><dl className="space-y-3">{Object.entries(profile.definitions).map(([metric, definition]) => <div key={metric}><dt className="font-bold">{metric}</dt><dd className="text-sm text-muted">{definition}</dd></div>)}</dl></Panel>
  </div>;
}
