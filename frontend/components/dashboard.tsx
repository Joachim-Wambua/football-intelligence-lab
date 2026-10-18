"use client";
import { useState } from "react";
import useSWR from "swr";
import { z } from "zod";
import { apiGet } from "@/lib/api";
import { competitionSchema, matchSchema, summarySchema, playerSchema, type Competition, type Team } from "@/lib/contracts";
import { ErrorState, LoadingState, MetricCard, Panel, SelectField } from "./ui";
import { ShotComparison } from "./charts";
import { ProgressivePassing } from "./progressive-passing";
import { ExpectedThreat } from "./expected-threat";

const options = { shouldRetryOnError: false, revalidateOnFocus: false };

export function Dashboard() {
  const query = useSWR("/competitions", path => apiGet(path, z.array(competitionSchema)), options);
  const [selected, setSelected] = useState("");
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState label="Loading available competitions…"/>;
  if (!query.data.length) return <Panel title="No competitions available">The provider has no available datasets.</Panel>;
  const key = (item: Competition) => `${item.competition_id}:${item.season_id}`;
  const initial = query.data.find(item => item.competition_id === 9 && item.season_id === 281) ?? query.data[0];
  const competition = query.data.find(item => key(item) === selected) ?? initial;
  return <div className="mx-auto max-w-[1440px] space-y-7">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="mb-2 text-xs font-bold uppercase tracking-[.2em] text-muted">Football intelligence / Match centre</p><h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Read the game.</h1><p className="mt-3 text-sm text-muted">From match events to a clearer picture of performance.</p></div><span className="rounded-full border border-border bg-surface px-4 py-2 text-xs font-bold">StatsBomb · Open data</span></header>
    <Panel title="Match selection" subtitle="Choose the context for your analysis."><SelectField label="Competition and season" value={key(competition)} onChange={setSelected}>{query.data.map(item => <option key={key(item)} value={key(item)}>{item.country_name ? `${item.country_name} · ` : ""}{item.competition_name} · {item.season_name}{item.competition_gender ? ` · ${item.competition_gender}` : ""}</option>)}</SelectField>
      {competition.competition_id === 9 && competition.season_id === 281 && <p className="mt-3 text-xs text-muted">This Bundesliga release covers Bayer Leverkusen matches, not the complete league.</p>}</Panel>
    <Matches key={key(competition)} competition={competition}/>
    <footer className="border-t border-border pt-5 text-xs leading-relaxed text-muted">Data provided by <a className="underline" href="https://github.com/statsbomb/open-data">StatsBomb Open Data</a>. Follow the dataset’s attribution and usage terms. Statistics are supplied by the shared Python analytics API.</footer>
  </div>;
}

function Matches({ competition }: { competition: Competition }) {
  const path = `/matches?competition_id=${competition.competition_id}&season_id=${competition.season_id}`;
  const query = useSWR(path, path => apiGet(path, z.array(matchSchema)), options);
  const [selected, setSelected] = useState<number>();
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState label="Loading available matches…"/>;
  if (!query.data.length) return <Panel title="No matches available">Choose another competition or season.</Panel>;
  const match = query.data.find(item => item.match_id === selected) ?? query.data[0];
  return <><SelectField label="Match" value={match.match_id} onChange={value => setSelected(Number(value))}>{query.data.map(item => <option key={item.match_id} value={item.match_id}>{item.match_date} · {item.home_team} vs {item.away_team}</option>)}</SelectField>
    <div className="flex flex-wrap items-center justify-between gap-4"><h2 className="text-xl font-bold">{match.home_team} <span className="text-muted">vs</span> {match.away_team}</h2><p className="rounded-lg bg-raised px-4 py-2 text-lg font-bold tabular-nums" aria-label="Match score">{match.home_score ?? "–"} : {match.away_score ?? "–"}</p></div>
    <MatchAnalysis key={match.match_id} matchId={match.match_id}/></>;
}

function MatchAnalysis({ matchId }: { matchId: number }) {
  const query = useSWR(`/matches/${matchId}/summary`, path => apiGet(path, summarySchema), options);
  const [selected, setSelected] = useState<number>();
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState/>;
  if (!query.data.teams.length) return <Panel title="No team data">No named teams were returned for this match.</Panel>;
  const team = query.data.teams.find(item => item.team_id === selected) ?? query.data.teams[0];
  return <><SelectField label="Team" value={team.team_id} onChange={value => setSelected(Number(value))}>{query.data.teams.map(item => <option key={item.team_id} value={item.team_id}>{item.team}</option>)}</SelectField>
    <section id="overview" aria-label="Team overview" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="Passes attempted" value={team.passing.attempted} detail={`${team.passing.completed} completed passes`}/>
      <MetricCard label="Pass completion" value={`${team.passing.completion_pct.toFixed(1)}%`} detail="All recorded pass types"/>
      <MetricCard label="Shots" value={team.shots} detail={`${team.shot_goals} goals from shot events`}/>
      <MetricCard label="Recorded xG" value={team.recorded_xg?.toFixed(2) ?? "Unavailable"} detail={`${team.shots_with_xg}/${team.shots} shots have provider xG`}/>
    </section>
    <Panel title="Attacking output" subtitle="Shot volume and outcomes across both teams"><ShotComparison teams={query.data.teams}/></Panel>
    <Players key={`${matchId}-${team.team_id}`} matchId={matchId} team={team}/>
    <ExpectedThreat key={`xt-${matchId}-${team.team_id}`} matchId={matchId} teamId={team.team_id}/></>;
}

function Players({ matchId, team }: { matchId: number; team: Team }) {
  const query = useSWR(`/matches/${matchId}/teams/${team.team_id}/players`, path => apiGet(path, z.array(playerSchema)), options);
  const [selected, setSelected] = useState<number>();
  if (query.error) return <ErrorState message={query.error.message} retry={() => void query.mutate()}/>;
  if (!query.data) return <LoadingState label="Loading player statistics…"/>;
  if (!query.data.length) return <Panel id="players" title="No player statistics">No named player events were returned for this team.</Panel>;
  const player = query.data.find(item => item.player_id === selected) ?? query.data[0];
  return <><Panel id="players" title="Player comparison" subtitle={`${team.team} · Event-observed players only; no per-90 estimates`}>
    <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable player comparison"><table className="w-full text-sm"><caption className="sr-only">Player performance for {team.team}. Missing xG is shown as unavailable.</caption><thead><tr>{["Player", "Passes", "Completed", "Completion", "Shots", "Goals", "xG", "Dribbles won", "Interceptions won"].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{query.data.map(item => <tr key={item.player_id}><th scope="row" className="text-foreground normal-case">{item.player}</th><td>{item.passes}</td><td>{item.completed_passes}</td><td>{item.pass_completion_pct.toFixed(1)}%</td><td>{item.shots}</td><td>{item.goals}</td><td>{item.xg?.toFixed(2) ?? "Unavailable"}</td><td>{item.successful_dribbles}</td><td>{item.successful_interceptions}</td></tr>)}</tbody></table></div>
  </Panel>
  <ProgressivePassing matchId={matchId} teamId={team.team_id} players={query.data} player={player} onSelectPlayer={setSelected}/></>;
}
