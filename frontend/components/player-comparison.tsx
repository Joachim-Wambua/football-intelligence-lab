"use client";
import { useId, useState } from "react";
import type { PlayerCatalogueData, PlayerIdentity } from "@/lib/player-contracts";
import { Panel, SelectField } from "./ui";

type View = "total" | "per90";
const valueText = (value: number | null, estimated = false) => {
  if (value === null) return "Unavailable";
  const rounded = value.toFixed(estimated ? 4 : 2);
  // Small nonzero model changes must not become a displayed measured zero.
  return value !== 0 && Number(rounded) === 0 ? value.toExponential(2) : rounded;
};
const playerLabel = (player: PlayerIdentity) => `${player.player} · ID ${player.player_id}`;
const groups = [
  { title: "Observed counts and passing geometry", kinds: ["observed", "geometry"] },
  { title: "Provider xG estimates", kinds: ["provider_estimate"] },
  { title: "Experimental xT estimates", kinds: ["experimental_estimate"] },
];

/** Select distinct provider identities from ONE server-prepared collection.
 * The catalogue already contains both aggregates, so selection does not fetch
 * another profile or recompute metrics. Component keys reset choices/view when
 * context changes. Matching files does not imply equal minutes or equal roles.
 */
export function PlayerComparison({ catalogue }: { catalogue: PlayerCatalogueData }) {
  const [firstId, setFirstId] = useState<number>();
  const [secondId, setSecondId] = useState<number>();
  const [firstSearch, setFirstSearch] = useState(""), [secondSearch, setSecondSearch] = useState("");
  const [view, setView] = useState<View>("total");
  const search = (player: PlayerIdentity, text: string) => `${player.player} ${player.aliases.join(" ")} ${player.player_id}`.toLocaleLowerCase().includes(text.toLocaleLowerCase());
  const firstOptions = catalogue.players.filter(player => search(player, firstSearch));
  const first = firstOptions.find(player => player.player_id === firstId) ?? firstOptions[0];
  const secondOptions = catalogue.players.filter(player => player.player_id !== first?.player_id && search(player, secondSearch));
  const second = secondOptions.find(player => player.player_id === secondId) ?? secondOptions[0];
  const context = catalogue.context;
  return <div className="space-y-6">
    <Panel title="Compare two players" subtitle="Same competition, season, team and selected files. Descriptive evidence, not scouting ratings.">
      <p className="mb-4 text-sm">Competition {context.competition_id} · Season {context.season_id} · Team {context.team_id}. Selected match IDs: {context.requested_match_ids.join(", ")}. Included IDs: {context.included_match_ids.join(", ")}. {context.sample_label}.</p>
      {!!context.failed_matches.length && <p className="mb-4 font-bold">Selected-file gaps: {context.failed_matches.map(row => `${row.match_id}: ${row.status}`).join("; ")}. Totals cover the included subset; comparison bars and rates are withheld.</p>}
      {!!context.lineups_unavailable_match_ids.length && <p className="mb-4 text-sm">Lineups unavailable for match IDs: {context.lineups_unavailable_match_ids.join(", ")}.</p>}
      <div className="grid gap-5 sm:grid-cols-2">
        <ComparisonSelection label="First player" search={firstSearch} onSearch={setFirstSearch} players={firstOptions} selected={first} onSelect={setFirstId}/>
        <ComparisonSelection label="Second player" search={secondSearch} onSearch={setSecondSearch} players={secondOptions} selected={second} onSelect={setSecondId}/>
      </div>
      {catalogue.players.length < 2 && <p role="status" className="mt-4">At least two distinct player IDs are required in this collection.</p>}
      {first && second && <div className="mt-5"><SelectField label="Comparison view" value={view} onChange={value => setView(value as View)}><option value="total">Totals in included matches</option><option value="per90">Per 90 elapsed pitch minutes</option></SelectField></div>}
    </Panel>
    {first && second && <>
      <Panel title="Evidence and exposure" subtitle="Same files can contain different appearances, minutes and positions. No primary position is inferred.">
        <div className="grid gap-5 sm:grid-cols-2">{[first, second].map(player => <PlayerEvidence key={player.player_id} player={player} matchIds={context.included_match_ids}/>)}</div>
        <p className="mt-4 text-sm text-muted">Minutes include recorded added time and exclude intervals/shootouts. Per90 pools counts divided by their matching elapsed minutes; it does not remove role, opponent, game-state, selection or small-sample bias. No percentile reference population or combined rating is used.</p>
      </Panel>
      {groups.map(group => <MetricGroup key={group.title} title={group.title} kinds={group.kinds} first={first} second={second} view={view}/>)}
      <Panel title="Methodology and model provenance">
        <p className="mb-3 text-sm">Covered-only xG/xT and incomplete progression counts remain visible as qualified totals. Their bars and comparison rates are withheld until full recorded coverage; no arbitrary minimum-coverage cutoff is invented. Unsuccessful/ineligible xT moves can be intentionally unrated. A withheld bar is not zero contribution.</p>
        <p className="mb-3 font-bold">{catalogue.model.limitations}</p>
        <p className="break-all text-xs">Model {catalogue.model.status} · ID {catalogue.model.model_id ?? "Unavailable"} · {catalogue.model.training_matches ?? "Unknown"} training / {catalogue.model.held_out_matches ?? "Unknown"} held out · {catalogue.model.shot_zones ?? "Unknown"}/{catalogue.model.total_zones ?? "Unknown"} shot-observed zones.</p>
        <details className="mt-4"><summary className="min-h-11 cursor-pointer font-bold">Shared metric definitions</summary><dl className="space-y-3">{Object.entries(catalogue.definitions).map(([metric, definition]) => <div key={metric}><dt className="font-bold">{metric}</dt><dd className="text-sm text-muted">{definition}</dd></div>)}</dl></details>
      </Panel>
    </>}
  </div>;
}
function ComparisonSelection({ label, search, onSearch, players, selected, onSelect }: {
  label: string; search: string; onSearch: (value: string) => void; players: PlayerIdentity[];
  selected?: PlayerIdentity; onSelect: (value: number) => void;
}) {
  const id = useId();
  return <div><label htmlFor={id} className="mb-2 block text-sm font-bold">Search {label.toLowerCase()}</label><input id={id} type="search" className="mb-3 min-h-11 w-full rounded border border-border bg-surface p-3" value={search} onChange={event => onSearch(event.target.value)}/>
    {selected ? <SelectField label={label} value={selected.player_id} onChange={value => onSelect(Number(value))}>{players.map(player => <option key={player.player_id} value={player.player_id}>{playerLabel(player)}</option>)}</SelectField> : <p role="status">No matching distinct {label.toLowerCase()}. Clear the search or change the collection.</p>}
  </div>;
}
function PlayerEvidence({ player, matchIds }: { player: PlayerIdentity; matchIds: number[] }) {
  const aggregate = player.aggregate;
  return <article className="rounded-lg border border-border p-4" aria-label={`Evidence for ${playerLabel(player)}`}>
    <h3 className="font-bold">{playerLabel(player)}</h3><p className="mt-2 text-sm">{player.team} · All recorded positions: {player.positions.join(", ") || "Unavailable"}.</p>
    <p className="mt-2 text-sm">Confirmed appearances: {aggregate.appearances}; unknown: {aggregate.unknown_appearances}.</p>
    <p className="text-sm">Verified total minutes: {valueText(aggregate.minutes)}. Known minutes: {valueText(aggregate.known_minutes)}. Reliable exposure: {aggregate.minutes_covered_matches} / {matchIds.length} included player-match records.</p>
    <p className="text-sm">Included match IDs: {matchIds.join(", ")}. Per90 denominator match IDs: {aggregate.per90_match_ids.join(", ") || "Unavailable"}.</p>
    <p className="mt-2 text-sm">Provider xG: {aggregate.statistics.shots_with_xg}/{aggregate.statistics.shots} shots covered. Passing geometry: {aggregate.statistics.progressive_valid_geometry}/{aggregate.statistics.passes}. Experimental xT: {aggregate.statistics.xt_rated_actions}/{aggregate.statistics.xt_attempted_actions} moves rated.</p>
  </article>;
}
function MetricGroup({ title, kinds, first, second, view }: { title: string; kinds: string[]; first: PlayerIdentity; second: PlayerIdentity; view: View }) {
  const entries = Object.entries(first.aggregate.comparison_evidence).filter(([, row]) => kinds.includes(row.kind));
  if (entries.some(([key]) => !second.aggregate.comparison_evidence[key])) return <p role="alert">Comparison evidence does not contain matching metric definitions.</p>;
  return <Panel title={title} subtitle={view === "total" ? "Recorded/covered totals; different playing opportunity remains visible." : "Python-qualified per90; unknown or zero exposure is unavailable."}>
    <div className="space-y-6">{entries.map(([metric, left]) => {
      const right = second.aggregate.comparison_evidence[metric];
      const estimated = left.kind.endsWith("estimate");
      const leftValue = view === "total" ? left.total : left.per90, rightValue = view === "total" ? right.total : right.per90;
      return <section key={metric} aria-label={`${left.label} comparison`}>
        <h3 className="font-bold">{left.label}</h3><p className="mt-1 text-xs text-muted">{left.definition}</p>
        <ComparisonBars label={left.label} names={[playerLabel(first), playerLabel(second)]} values={view === "total" ? [left.chart_total, right.chart_total] : [left.per90, right.per90]} estimated={estimated}/>
        <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={`${left.label} numeric values`}><table className="w-full text-sm"><caption className="sr-only">{left.label} · {view === "total" ? "totals" : "per90"}</caption><thead><tr><th scope="col">Player</th><th scope="col">{view === "total" ? "Total / covered sum" : "Per90"}</th><th scope="col">Evidence qualification</th></tr></thead><tbody>{[{ identity: first, evidence: left, value: leftValue }, { identity: second, evidence: right, value: rightValue }].map(({ identity, evidence, value }) => {
          return <tr key={identity.player_id}><th scope="row">{playerLabel(identity)}</th><td>{valueText(value, estimated)}</td><td style={{ whiteSpace: "normal", minWidth: "18rem" }}>{evidence.status === "complete" ? "Complete recorded coverage" : evidence.status.replaceAll("_", " ")}{evidence.coverage_total !== null && ` · ${evidence.coverage_count}/${evidence.coverage_total} covered`}. {evidence.note}</td></tr>;
        })}</tbody></table></div>
      </section>;
    })}</div>
  </Panel>;
}

/** Draw two independent bars on the same zero-centred scale for ONE metric.
 * Only SVG geometry is calculated here. Python supplies every football value,
 * coverage decision and per90 rate. Null renders text with no zero marker;
 * genuine zero renders a point at the baseline. Signed xT extends left/right.
 * Focusable labelled groups and a numeric table avoid color-only interpretation.
 */
export function ComparisonBars({ label, names, values, estimated = false }: { label: string; names: [string, string]; values: [number | null, number | null]; estimated?: boolean }) {
  const uid = useId();
  const scale = Math.max(Number.EPSILON, ...values.filter((value): value is number => value !== null).map(Math.abs));
  return <figure><svg viewBox="0 0 600 110" role="group" aria-labelledby={uid} className="my-3 w-full rounded border border-border bg-raised">
    <title id={uid}>{label}: side-by-side bars, one shared scale; negative left, positive right</title>
    <line x1="300" y1="8" x2="300" y2="102" stroke="var(--muted)" aria-hidden="true"/>
    {values.map((value, index) => {
      const width = value === null ? 0 : Math.abs(value) / scale * 170;
      const y = 23 + index * 48;
      return <g key={index} tabIndex={0} role="img" aria-label={`${names[index]}: ${valueText(value, estimated)}${value === null ? " for chart; inspect evidence qualification in table" : ""}`}>
        <text x="8" y={y + 13} fill="var(--foreground)" fontSize="13">{index === 0 ? "A" : "B"}</text>
        {value === null ? <text x="310" y={y + 13} fill="var(--foreground)" fontSize="13">Unavailable</text> : <>
          {value === 0 ? <circle data-zero="true" cx="300" cy={y+9} r="3" fill="var(--foreground)"/> : <rect data-bar="true" x={value < 0 ? 300-width : 300} y={y} width={width} height="18" fill={index === 0 ? "var(--foreground)" : "none"} stroke="var(--foreground)" strokeWidth="2" strokeDasharray={index === 0 ? undefined : "5 2"}/>}
          <text x="490" y={y + 13} fill="var(--foreground)" fontSize="13">{valueText(value, estimated)}</text>
        </>}
      </g>;
    })}
  </svg><figcaption className="text-xs text-muted">A: {names[0]}; B: {names[1]}. Solid and outlined bars use the same metric scale.</figcaption></figure>;
}
