export type MatchSelection = { competitionId?: number; seasonId?: number; matchId?: number; teamId?: number };
type Query = Record<string, string | string[] | undefined>;
const positiveId = (value: string | string[] | undefined) => typeof value === "string" && /^[1-9]\d*$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : undefined;

/** Restore a hierarchy, never a free-floating child ID in a fallback context.
 * A match requires an explicit competition/season pair; team requires match.
 * Repeated, unsafe, fractional and missing IDs fall back at their own level.
 * Catalogue membership is checked later, when the real available context loads.
 */
export function readMatchSelection(query: Query): MatchSelection {
  const competitionId = positiveId(query.competition_id), seasonId = positiveId(query.season_id);
  if (!competitionId || !seasonId) return {};
  const matchId = positiveId(query.match_id);
  return { competitionId, seasonId, ...(matchId ? { matchId, teamId: positiveId(query.team_id) } : {}) };
}

export function normalizeMatchSelection(selection: MatchSelection = {}): MatchSelection {
  return readMatchSelection({ competition_id: String(selection.competitionId), season_id: String(selection.seasonId),
    match_id: String(selection.matchId), team_id: String(selection.teamId) });
}
