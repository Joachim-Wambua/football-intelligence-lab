import { z } from "zod";
const finite = z.number().finite(), count = finite.int().nonnegative(), id = finite.int().positive();
export const xtModelSchema = z.object({
  model_id: z.string(), artifact_version: z.literal(1), nx: id, ny: id,
  surface: z.array(z.array(finite.min(0).max(1))), shot_counts: z.array(z.array(count)),
  coordinate_system: z.literal("StatsBomb 120x80 attacking right"), provider: z.string(), provenance: z.string(), trained_at: z.string(),
  competition_id: id, season_id: id, fallback: z.string(), experimental: z.literal(true),
  tolerance: finite.positive(), iterations: id, final_residual: finite.nonnegative(), manifest_sha256: z.string(), event_sha256: z.record(z.string(), z.string()),
  coverage: z.object({ train_ids: z.array(id), held_out_ids: z.array(id), published_matches: count, locally_eligible_matches: count,
    training_shots: count, training_goals: count, shot_zones: count, total_zones: count }),
}).refine(m => m.surface.length === m.ny && m.surface.every(row => row.length === m.nx) && m.shot_counts.length === m.ny && m.shot_counts.every(row => row.length === m.nx), "Grid dimensions must match the saved surface");
export const xtPlayersSchema = z.object({ model_id: z.string(), match_id: id, team_id: id, players: z.array(z.object({
  player_id: id, player: z.string(), action_count: count, rated_action_count: count, rated_passes: count, rated_carries: count, positive_xt: finite.nullable(), net_xt: finite.nullable(),
})) });
export const xtActionSchema = z.object({ event_index: count, id: z.string().nullable().optional(), type: z.enum(["Pass", "Carry"]),
  player_id: id.nullable(), player: z.string().nullable(), team_id: id, period: count.nullable().optional(), minute: count.nullable().optional(), second: count.nullable().optional(),
  successful: z.boolean(), x: finite.nullable(), y: finite.nullable(), end_x: finite.nullable(), end_y: finite.nullable(), xt: finite.nullable() });
export const xtActionsSchema = z.object({ model_id: z.string(), match_id: id, team_id: id, total: count, offset: count, limit: id.max(500), actions: z.array(xtActionSchema).max(500) });
export type XTModel = z.infer<typeof xtModelSchema>;
export type XTAction = z.infer<typeof xtActionSchema>;

/** Select API records by action type and strict sign; never recalculate xT.
 * Null and genuine zero remain in "all" but neither is positive nor negative.
 */
export function filterXTActions(actions: XTAction[], type: string, sign: string): XTAction[] {
  return actions.filter(a => (type === "all" || a.type === type) && (sign === "all" || a.xt !== null && (sign === "positive" ? a.xt > 0 : a.xt < 0)));
}
export function formatXT(value: number | null): string {
  return value === null ? "Unrated" : `${value > 0 ? "+" : ""}${value.toFixed(4)}`;
}
