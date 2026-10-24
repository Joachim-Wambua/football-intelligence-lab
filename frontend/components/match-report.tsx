"use client";
import { useState, type ReactNode } from "react";
import useSWR from "swr";
import { loadMatchReport, reportHref, type MatchReportData, type ReportSelection } from "@/lib/match-report";
import { formatXT } from "@/lib/xt-contracts";
import type { Shot } from "@/lib/contracts";
import { ErrorState, LoadingState } from "./ui";

const options = { shouldRetryOnError: false, revalidateOnFocus: false, revalidateOnReconnect: false, keepPreviousData: false };
const metricLabels: Record<string, string> = {
  shots: "Recorded shots", xg_coverage: "Provider xG coverage", recorded_xg: "Recorded provider xG (estimate)",
  completed_progressive_leader: "Completed progressive-pass leader",
  experimental_positive_xt_leader: "Experimental positive xT leader (estimate)",
};

/** Remount export feedback on URL context changes; SWR keys isolate late responses. */
export function MatchReport({ selection }: { selection: ReportSelection }) {
  return <ReportSnapshot key={reportHref(selection)} selection={selection}/>;
}

function ReportSnapshot({ selection }: { selection: ReportSelection }) {
  const query = useSWR(["match-report", reportHref(selection)], () => loadMatchReport(selection), options);
  const [feedback, setFeedback] = useState("");
  const ready = !!query.data && !query.error && !query.isValidating;

  /** Browser print is user-controlled: requesting the dialog does not prove a PDF
   * was saved. No server export, theme change, or automatic printing is involved.
   */
  function printReport() {
    if (!ready) return;
    try { window.print(); setFeedback("Print dialog requested. Choose Save as PDF to save this report."); }
    catch { setFeedback("Printing is unavailable. Try your browser’s Print command."); }
  }
  async function copyReportLink() {
    try {
      await navigator.clipboard.writeText(new URL(reportHref(selection), window.location.origin).href);
      setFeedback("Report link copied. The recipient needs access to this application and its data API.");
    } catch { setFeedback("Link could not be copied. Copy this page’s address from your browser."); }
  }
  return <div className="report-page mx-auto max-w-5xl space-y-6">
    <div className="report-controls space-y-3">
      <a className="inline-block min-h-11 underline" href="/">Back to match workspace</a>
      <div className="flex flex-wrap gap-3">
        <button className="min-h-11 rounded-lg bg-accent px-4 font-bold text-accent-foreground disabled:opacity-50" disabled={!ready} onClick={printReport}>Print / Save as PDF</button>
        <button className="min-h-11 rounded-lg border border-border px-4" onClick={() => void copyReportLink()}>Copy report link</button>
        <button className="min-h-11 rounded-lg border border-border px-4 disabled:opacity-50" disabled={query.isValidating} onClick={() => { setFeedback(""); void query.mutate(); }}>Refresh report</button>
      </div>
      <p className="text-sm text-muted">Use your browser’s Save as PDF destination. Check the print preview; paper size and page breaks depend on your browser. Shared links reopen current evidence; PDFs preserve this snapshot.</p>
      <p role="status" aria-live="polite">{feedback}</p>
    </div>
    {query.error ? <ErrorState message={query.error.message} retry={() => void query.mutate()}/> : !query.data || query.isValidating ? <LoadingState label="Preparing report evidence…"/> : <ReportContent data={query.data}/>}
  </div>;
}

function ReportSection({ title, children }: { title: string; children: ReactNode }) {
  return <section className="report-section rounded-xl border border-border bg-surface p-5 sm:p-7"><h2 className="mb-4 text-xl font-bold">{title}</h2>{children}</section>;
}
function MissingEvidence({ message }: { message: string }) {
  return <p className="report-gap rounded border border-border p-3">Section unavailable: {message} This is missing evidence, not zero activity.</p>;
}

/** Presentation of server-owned totals and ordering, never a new rating or model.
 * xG and xT are estimates in separate sections from measured outcomes. Missing
 * evidence is printable and model hashes must match before estimates are mixed.
 */
export function ReportContent({ data }: { data: MatchReportData }) {
  const { match, team, summary, progression, shots, insights, model, xt, selection } = data;
  const modelReady = !!model.data && !!xt.data && model.data.model_id === xt.data.model_id;
  const insightMismatch = !!insights.data?.observations.some(row => row.model_id && (!modelReady || row.model_id !== model.data?.model_id));
  const incomplete = !!shots.error || !!progression.error || !!insights.error || !modelReady || insightMismatch;
  return <article className="match-report space-y-6" aria-label={`Match report: ${match.home_team} vs ${match.away_team}`}>
    <header className="report-section border-b border-border pb-6">
      <p className="text-xs font-bold uppercase tracking-widest text-muted">Football Intelligence Lab · Match report</p>
      <h1 className="my-3 text-3xl font-bold">{match.home_team} vs {match.away_team}</h1>
      <p className="text-lg">{match.match_date} · Provider score: {match.home_score ?? "Unavailable"} : {match.away_score ?? "Unavailable"}</p>
      <p>{data.competition ? `${data.competition.competition_name} · ${data.competition.season_name}` : `Competition ${selection.competitionId} · Season ${selection.seasonId}`} · Match ID {match.match_id}</p>
      <p className="mt-2 font-bold">Selected team: {team.team} · Team ID {team.team_id}</p>
      <p className="mt-2 text-xs text-muted">Evidence retrieved (UTC): {data.retrievedAt}. Full recorded match; no workspace player filters applied.</p>
      {incomplete && <p className="report-gap mt-4 rounded border border-border p-3 font-bold">Incomplete report — unavailable or incompatible evidence is labelled below.</p>}
    </header>

    <ReportSection title="Measured match outcomes">
      <div className="report-table overflow-x-auto"><table className="w-full text-sm">
        <caption className="text-left text-sm text-muted">Recorded events for both teams; shot goals exclude own goals and may differ from the provider score.</caption>
        <thead><tr>{["Team", "Shots", "Shot goals", "Completed / attempted passes", "Completion"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
        <tbody>{summary.teams.map(row => <tr key={row.team_id}><th scope="row">{row.team}</th><td>{row.shots}</td><td>{row.shot_goals}</td><td>{row.passing.completed} / {row.passing.attempted}</td><td>{row.passing.completion_pct.toFixed(1)}%</td></tr>)}</tbody>
      </table></div>
      <p className="mt-3 text-sm text-muted">All recorded periods and pass types, including set pieces, extra time and shootouts where supplied. Event-observed players only; no minutes or per-90 estimates.</p>
    </ReportSection>

    <ReportSection title="Shot analysis and provider xG estimates">
      <p className="mb-4">{team.team}: {team.shots} recorded shots, {team.shot_goals} shot goals. Recorded provider xG: <strong>{team.recorded_xg?.toFixed(2) ?? "Unavailable"}</strong>. Coverage: <strong>{team.shots_with_xg} / {team.shots} shots</strong>.</p>
      <p className="mb-4 text-sm text-muted">xG is a provider model estimate for each shot, not a measured goal. The total sums available values only; incomplete coverage is a partial total. No covered shots means unavailable, including 0/0 when no shots exist.</p>
      {shots.data ? <ReportShots shots={shots.data}/> : <MissingEvidence message={shots.error}/>}
    </ReportSection>

    <ReportSection title="Progressive-passing leaders · measured geometry">
      {progression.data ? <>
        <p className="mb-4 text-sm text-muted">Completed progressive passes reduce distance to goal centre ({progression.data.definition.goal_x}, {progression.data.definition.goal_y}) by at least {progression.data.definition.threshold_m} metres-equivalent on an assumed {progression.data.definition.pitch_length_m} × {progression.data.definition.pitch_width_m} m pitch. Distances are estimates of geometry, not measured pitch metres. Top five server-ranked passers by completed progressive count, attempts, then player ID; zero counts do not imply a qualifying leader.</p>
        {!progression.data.players.length ? <p>No named passers recorded.</p> : <div className="report-table overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Selected-team progressive passing, default API definition</caption>
          <thead><tr>{["Player", "Completed progressive", "Progressive attempts", "All passes", "Valid geometry"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
          <tbody>{progression.data.players.slice(0, 5).map(row => <tr key={row.player_id}><th scope="row">{row.player}</th><td>{row.completed_progressive}</td><td>{row.progressive_attempts}</td><td>{row.passes}</td><td>{row.valid_geometry} / {row.passes}</td></tr>)}</tbody>
        </table></div>}
      </> : <MissingEvidence message={progression.error}/>}
    </ReportSection>

    <ReportSection title="Experimental xT · model estimates">
      <p className="mb-4 font-bold">Experimental, action-conditioned estimates. Not calibrated possession-goal probabilities, player ratings or coach recommendations. Small Leverkusen sample; not broadly representative.</p>
      {modelReady && model.data && xt.data ? <>
        <p className="mb-3 text-sm">Frozen model fitted offline, never during API requests. {model.data.coverage.train_ids.length} training matches, {model.data.coverage.held_out_ids.length} held out; {model.data.coverage.shot_zones} / {model.data.coverage.total_zones} zones have observed training shots ({model.data.coverage.training_shots} shots). Sparse zones use fallback: {model.data.fallback}.</p>
        <p className="mb-3 break-all text-xs">Model SHA256: {model.data.model_id} · Trained: {model.data.trained_at} · Provider: {model.data.provider} · <a href={model.data.provenance} className="underline">Model data provenance</a></p>
        {!xt.data.players.length ? <p>No identified move-makers recorded.</p> : <div className="report-table overflow-x-auto"><table className="w-full text-sm"><caption className="text-left text-sm text-muted">Top five in API order: positive xT, net xT, then ID. Null totals are unrated.</caption>
          <thead><tr>{["Player", "Positive xT", "Net xT", "Rated / attempted moves"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
          <tbody>{xt.data.players.slice(0, 5).map(row => <tr key={row.player_id}><th scope="row">{row.player}</th><td>{formatXT(row.positive_xt)}</td><td>{formatXT(row.net_xt)}</td><td>{row.rated_action_count} / {row.action_count}</td></tr>)}</tbody>
        </table></div>}
      </> : <MissingEvidence message={model.error ?? xt.error ?? "Model versions differ; refresh before comparing estimates."}/>}
    </ReportSection>

    <ReportSection title="Evidence-based match insights">
      {insights.data ? <><ul className="space-y-4">{insights.data.observations.filter(row => !row.model_id || modelReady && row.model_id === model.data?.model_id).map(row => <li key={row.metric} className="report-observation">
        <h3 className="font-bold">{metricLabels[row.metric] ?? row.metric}: {row.player && `${row.player} · `}{row.value ?? "Unavailable"}</h3>
        {row.denominator !== null && <p className="text-sm">Denominator / coverage count: {row.denominator}</p>}
        <p className="text-sm text-muted">Metric: {row.metric}. {row.definition}</p>
        {row.model_id && <p className="break-all text-xs">Model: {row.model_id}</p>}
      </li>)}</ul>{!insights.data.observations.length && <p>No observations returned.</p>}{insightMismatch && <MissingEvidence message="Experimental insight model could not be verified against this report; its values are omitted."/>}{insights.data.xt_status === "unavailable" && <p>Experimental xT insight unavailable; observed insights are retained.</p>}</> : <MissingEvidence message={insights.error}/>}
    </ReportSection>

    <ReportSection title="Metric definitions and limitations">
      <dl className="space-y-4 text-sm">
        <div><dt className="font-bold">Pass completion</dt><dd>100 × completed / all attempted passes; API convention is 0% for no attempts. StatsBomb omits outcome for completed passes. Invalid geometry remains in the attempt denominator.</dd></div>
        <div><dt className="font-bold">Progression</dt><dd>Python scales x by pitch length/120 and y by pitch width/80 before measuring Euclidean distance to goal. Progression = start distance − end distance. For example, a centre-line pass from x=40 to x=60 reduces distance by 17.5 m-equivalent on a 105 m pitch. Geometric attempts can be unsuccessful; completed progressive also requires completion. Missing geometry is unclassified.</dd></div>
        <div><dt className="font-bold">xG coverage</dt><dd>Shots with a valid provider probability / all shots. For example, 2/3 means one missing value. A recorded zero remains zero; missing xG is never filled with zero.</dd></div>
        <div><dt className="font-bold">Experimental positive and net xT</dt><dd>Successful, eligible passes/carries are valued as frozen destination-zone value − origin-zone value. Positive xT sums positive rated changes; net xT includes negative changes. For +0.03, −0.01, 0 and null, positive is 0.03, net is 0.02, and rated coverage is 3/4. Unsuccessful, missing-geometry and ineligible moves stay unrated. Totals are not per-90 or causal evidence.</dd></div>
      </dl>
    </ReportSection>
    <footer className="report-section border-t border-border pt-5 text-xs leading-relaxed text-muted">
      <p>Data: <a className="underline" href="https://github.com/statsbomb/open-data">StatsBomb Open Data</a>, via statsbombpy and the shared Football Intelligence Lab Python analytics API. Follow StatsBomb attribution, logo and usage terms when sharing. Event counts and model coverage reflect the available provider records; absence is not evidence of no activity.</p>
      <p className="mt-2">Report link: <a className="underline break-all" href={reportHref(selection)}>{reportHref(selection)}</a>. Links reopen current data; this PDF is a snapshot of the evidence retrieved above. No tactical conclusions are inferred.</p>
    </footer>
  </article>;
}

/** Static provider-coordinate map and always-visible event table for printing.
 * Same 120×80 top-left-origin convention in every period: do not mirror the
 * away side or second half. Invalid locations are omitted only from the SVG.
 * Constant marker size avoids suggesting xG is an observed outcome.
 */
function ReportShots({ shots }: { shots: Shot[] }) {
  const visible = shots.filter(shot => shot.x !== null && shot.y !== null);
  return <>
    {!shots.length ? <p>No shot events recorded for this team.</p> : <>
      <figure className="report-shot-map mb-4">
        <svg viewBox="-5 -5 130 90" role="img" aria-label="Shot origins, attacking right; G squares are goals, circles are other shots" className="mx-auto w-full max-w-xl" style={{ background: "var(--pitch)" }}>
          <g fill="none" stroke="var(--pitch-line)" strokeWidth=".5" aria-hidden="true"><rect width="120" height="80"/><path d="M60 0V80 M120 18H102V62H120 M0 18H18V62H0"/><circle cx="60" cy="40" r="9.15"/></g>
          {visible.map(shot => shot.goal ? <g key={shot.event_index}><rect x={shot.x! - 2} y={shot.y! - 2} width="4" height="4" fill="var(--foreground)"/><text x={shot.x!} y={shot.y! + 1} textAnchor="middle" fontSize="3" fill="var(--surface)">G</text></g> : <circle key={shot.event_index} cx={shot.x!} cy={shot.y!} r="2" fill="none" stroke="var(--foreground)" strokeWidth=".7"/>)}
        </svg>
        <figcaption className="mt-2 text-xs text-muted">StatsBomb 120 × 80 units, attacking right in every period. G square = goal; circle = other shot. Constant marker size. {shots.length - visible.length} events omitted from the map for missing coordinates; retained below.</figcaption>
      </figure>
      <div className="report-table overflow-x-auto"><table className="w-full text-sm"><caption className="text-left text-sm text-muted">All selected-team shots, including unavailable measurements</caption>
        <thead><tr>{["Player", "Period / minute", "Outcome", "Origin (x, y)", "Provider xG (estimate)"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
        <tbody>{shots.map(shot => <tr key={shot.event_index}><th scope="row">{shot.player ?? "Unknown player"}</th><td>{shot.period ?? "Unknown"} / {shot.minute ?? "Unknown"}</td><td>{shot.goal ? "Goal" : "Other shot"}</td><td>{shot.x ?? "Unavailable"}, {shot.y ?? "Unavailable"}</td><td>{shot.xg?.toFixed(3) ?? "Unavailable"}</td></tr>)}</tbody>
      </table></div>
    </>}
  </>;
}
