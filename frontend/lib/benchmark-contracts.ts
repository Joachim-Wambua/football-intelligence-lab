import { z } from "zod";

// Reserved benchmark-v1 contract; Python owns qualification and ranking.
// There is deliberately no fetcher, route, radar, or client-side ranking.
const id = z.number().int().positive();
export const benchmarkPercentileSchema = z.object({
  metric: z.string(), value_per90: z.number().finite().nullable(),
  percentile: z.number().min(0).max(100).nullable(), sample_size: z.number().int().nonnegative(),
  status: z.enum(["available", "unavailable", "low_exposure", "insufficient_samples"]),
  higher_is_better: z.boolean(),
}).refine(row => (row.status === "available") === (row.percentile !== null)
  && (row.status !== "available" || (row.value_per90 !== null && row.sample_size > 0)),
  "Percentile availability must agree with value and reference support");
export const benchmarkSummarySchema = z.object({
  schema_version: z.literal("benchmark-v1"), dataset_version: z.string(),
  competition_id: id, season_id: id, team_id: id, player_id: id,
  position_group: z.string().nullable(), match_ids: z.array(id),
  reference_members: z.array(z.tuple([id, id])),
  minimum_minutes: z.number().finite().nonnegative(), minimum_samples: id,
  tie_policy: z.literal("mid_distribution_exact_ties"),
  percentiles: z.array(benchmarkPercentileSchema), limitations: z.array(z.string()),
});
export type BenchmarkSummary = z.infer<typeof benchmarkSummarySchema>;
