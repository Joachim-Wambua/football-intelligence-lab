import { z } from "zod";
import { apiGet } from "./api";
import { competitionSchema, matchSchema, summarySchema, shotSchema, teamProgressionSchema, insightsSchema } from "./contracts";
import { xtModelSchema, xtPlayersSchema } from "./xt-contracts";

export type ReportSelection = { matchId: number; competitionId: number; seasonId: number; teamId: number };
export type Evidence<T> = { data: T; error?: never } | { data?: never; error: string };

/** Stable identifiers in the URL identify a live report, not an immutable archive.
 * Require explicit context rather than silently choosing a different match/team.
 */
export function reportHref(selection: ReportSelection): string {
  return `/reports/${selection.matchId}?competition_id=${selection.competitionId}&season_id=${selection.seasonId}&team_id=${selection.teamId}`;
}

export function positiveReportId(value: string | string[] | undefined): number | null {
  if (typeof value !== "string" || !/^[1-9]\d*$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

async function evidence<T>(request: Promise<T>): Promise<Evidence<T>> {
  try { return { data: await request }; }
  catch (error) { return { error: error instanceof Error ? error.message : "Evidence unavailable." }; }
}

/** Assemble existing API contracts, without calculating football metrics.
 * Independent requests settle before export is enabled. Core context failures
 * block the report; optional failures remain explicit printable gaps. Numeric IDs
 * are checked as well as shapes so even a wrong-context valid response is rejected.
 * For example, a team-20 response cannot populate a team-10 report. xT artifact
 * identity is checked at rendering time before any model-based values are shown.
 */
export async function loadMatchReport(selection: ReportSelection) {
  const { matchId, teamId, competitionId, seasonId } = selection;
  const path = `/matches/${matchId}`;
  const teamPath = `${path}/teams/${teamId}`;
  const checkTeam = <T extends { match_id: number; team_id: number }>(data: T): T => {
    if (data.match_id !== matchId || data.team_id !== teamId) throw new Error("Report evidence belongs to another match or team.");
    return data;
  };
  const [competitions, matches, summary, shots, progression, insights, model, xt] = await Promise.all([
    evidence(apiGet("/competitions", z.array(competitionSchema))),
    apiGet(`/matches?competition_id=${competitionId}&season_id=${seasonId}`, z.array(matchSchema)),
    apiGet(`${path}/summary`, summarySchema),
    evidence(apiGet(`${path}/shots?team_id=${teamId}`, z.array(shotSchema)).then(rows => {
      if (rows.some(row => row.match_id !== matchId || row.team_id !== teamId)) throw new Error("Shot evidence belongs to another match or team.");
      return rows;
    })),
    evidence(apiGet(`${teamPath}/progressive-passing`, teamProgressionSchema).then(checkTeam)),
    evidence(apiGet(`${teamPath}/insights`, insightsSchema).then(checkTeam)),
    evidence(apiGet("/xt/model", xtModelSchema)),
    evidence(apiGet(`${teamPath}/xt/players`, xtPlayersSchema).then(checkTeam)),
  ]);
  const match = matches.find(row => row.match_id === matchId);
  const team = summary.teams.find(row => row.team_id === teamId);
  if (!match || !team || summary.match_id !== matchId) throw new Error("Match or team not found in this report context.");
  const competition = competitions.data?.find(row => row.competition_id === competitionId && row.season_id === seasonId);
  return { selection, match, competition, summary, team, shots, progression, insights, model, xt, retrievedAt: new Date().toISOString() };
}
export type MatchReportData = Awaited<ReturnType<typeof loadMatchReport>>;
