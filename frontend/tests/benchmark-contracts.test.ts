import { describe, expect, it } from "vitest";
import { benchmarkPercentileSchema, benchmarkSummarySchema } from "@/lib/benchmark-contracts";

describe("reserved benchmark-v1 evidence contracts", () => {
  const missing = { metric: "shots", value_per90: null, percentile: null,
    sample_size: 0, status: "unavailable", higher_is_better: true };
  it("retains missing ranks and genuine zero ranks distinctly", () => {
    expect(benchmarkPercentileSchema.parse(missing).percentile).toBeNull();
    expect(benchmarkPercentileSchema.parse({ ...missing, value_per90: 0, percentile: 0,
      status: "available", sample_size: 20 }).percentile).toBe(0);
    expect(benchmarkPercentileSchema.safeParse({ ...missing, percentile: 0 }).success).toBe(false);
    expect(benchmarkPercentileSchema.safeParse({ ...missing, status: "available" }).success).toBe(false);
  });
  it("requires an explicit version and reference population", () => {
    const summary = { schema_version: "benchmark-v1", dataset_version: "sha256",
      competition_id: 72, season_id: 107, team_id: 1, player_id: 2, position_group: null,
      match_ids: [1], reference_members: [], minimum_minutes: 450, minimum_samples: 20,
      tie_policy: "mid_distribution_exact_ties", percentiles: [missing], limitations: ["Tournament sample"] };
    expect(benchmarkSummarySchema.parse(summary).position_group).toBeNull();
    expect(benchmarkSummarySchema.safeParse({ ...summary, schema_version: "v0" }).success).toBe(false);
    expect(benchmarkSummarySchema.safeParse({ ...summary, reference_members: undefined }).success).toBe(false);
  });
});
