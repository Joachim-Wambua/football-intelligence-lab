import { z } from "zod";
const finite = z.number().finite(), count = finite.int().nonnegative(), id = finite.int().positive();
export const playerStatisticsSchema = z.object({ passes: count, completed_passes: count, completed_progressive_passes: count,
  progressive_valid_geometry: count, shots: count, goals: count, shots_with_xg: count, xg: finite.nullable(),
  successful_dribbles: count, successful_interceptions: count, xt_positive: finite.nullable(), xt_net: finite.nullable(),
  xt_rated_actions: count, xt_attempted_actions: count });
export const playerRatesSchema = z.object({ passes: finite.nullable(), completed_passes: finite.nullable(),
  completed_progressive_passes: finite.nullable(), shots: finite.nullable(), goals: finite.nullable(), xg: finite.nullable(),
  successful_dribbles: finite.nullable(), successful_interceptions: finite.nullable(), xt_positive: finite.nullable(), xt_net: finite.nullable() });
const positionSpellSchema = z.object({ position_id: count.nullable().optional(), position: z.string().nullable().optional(),
  from: z.string().nullable().optional(), to: z.string().nullable().optional(), from_period: id.max(5).nullable().optional(),
  to_period: id.max(5).nullable().optional(), start_reason: z.string().nullable().optional(), end_reason: z.string().nullable().optional() });
const aggregateSchema = z.object({ appearances: count, unknown_appearances: count, minutes: finite.nonnegative().nullable(),
  known_minutes: finite.nonnegative().nullable(), minutes_covered_matches: count, statistics: playerStatisticsSchema,
  per90: playerRatesSchema, per90_match_ids: z.array(id) });
const identitySchema = z.object({ player_id: id, player: z.string(), aliases: z.array(z.string()), team_id: id, team: z.string(),
  positions: z.array(z.string()), aggregate: aggregateSchema });
const contextSchema = z.object({ competition_id: id, season_id: id, team_id: id, requested_match_ids: z.array(id).min(1).max(5),
  included_match_ids: z.array(id), failed_matches: z.array(z.object({ match_id: id, status: z.string() })),
  lineups_unavailable_match_ids: z.array(id), available_catalogue_matches: count, sample_label: z.string() });
const modelSchema = z.object({ status: z.enum(["available", "unavailable"]), model_id: z.string().nullable(), training_matches: count.nullable(),
  held_out_matches: count.nullable(), shot_zones: count.nullable(), total_zones: count.nullable(), limitations: z.string() });
const common = { context: contextSchema, definitions: z.record(z.string(), z.string()), model: modelSchema };
export const playerCatalogueSchema = z.object({ ...common, players: z.array(identitySchema) });
export const playerProfileSchema = z.object({ ...common, identity: identitySchema, matches: z.array(z.object({
  match_id: id, match_date: z.string(), home_team: z.string(), away_team: z.string(), team_id: id, team: z.string(),
  positions: z.array(z.string()), position_history: z.array(positionSpellSchema), minutes: finite.nonnegative().nullable(),
  appeared: z.boolean().nullable(), minutes_status: z.string(), minutes_provenance: z.string(), statistics: playerStatisticsSchema,
  per90: playerRatesSchema, model_id: z.string().nullable() })) });
export type PlayerProfile = z.infer<typeof playerProfileSchema>;
export type PlayerCollection = { competitionId: number; seasonId: number; teamId: number; matchIds: number[] };

/** Canonical selection keys isolate collections and share server-cached profiles.
 * Selection by ID is interface behavior; all rates/rankings remain Python-owned.
 */
export function collectionQuery(context: PlayerCollection): string {
  const params = new URLSearchParams({ competition_id: String(context.competitionId), season_id: String(context.seasonId), team_id: String(context.teamId) });
  [...context.matchIds].sort((a, b) => a - b).forEach(id => params.append("match_ids", String(id)));
  return params.toString();
}

/** Reject even shape-valid evidence from a different selected collection. */
export function hasPlayerContext(response: z.infer<typeof contextSchema>, selected: PlayerCollection): boolean {
  return collectionQuery({ competitionId: response.competition_id, seasonId: response.season_id,
    teamId: response.team_id, matchIds: response.requested_match_ids }) === collectionQuery(selected);
}
