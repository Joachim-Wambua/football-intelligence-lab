import artifact from "../../artifacts/xt-v1.json";
import { xtModelSchema, type XTAction } from "@/lib/xt-contracts";

// Test the actual saved grid, rather than a plausible-looking synthetic heatmap.
export const xtModelFixture = xtModelSchema.parse({ model_id: "fixture-model", artifact_version: 1,
  nx: artifact.config.nx, ny: artifact.config.ny, surface: artifact.surface,
  shot_counts: artifact.surface.map((_, row) => artifact.diagnostics.shots.slice(row * 16, (row + 1) * 16)),
  coordinate_system: artifact.metadata.coordinate_system, provider: artifact.metadata.provider,
  provenance: artifact.metadata.provenance, trained_at: artifact.metadata.trained_at,
  competition_id: 9, season_id: 281, fallback: artifact.metadata.fallback, experimental: true,
  tolerance: artifact.config.tolerance, iterations: artifact.diagnostics.iterations,
  final_residual: artifact.diagnostics.residuals.at(-1), manifest_sha256: artifact.metadata.manifest_sha256, event_sha256: artifact.metadata.event_sha256,
  coverage: { train_ids: artifact.metadata.train_ids, held_out_ids: artifact.metadata.held_out_ids,
    published_matches: 34, locally_eligible_matches: 8, training_shots: 159, training_goals: 25, shot_zones: 26, total_zones: 192 },
});
export const xtPlayersFixture = { model_id: "fixture-model", match_id: 1, team_id: 10,
  players: [{ player_id: 100, player: "Player A", action_count: 4, rated_action_count: 3,
    rated_passes: 2, rated_carries: 1, positive_xt: .3, net_xt: .2 },
  { player_id: 101, player: "Unrated player", action_count: 1, rated_action_count: 0,
    rated_passes: 0, rated_carries: 0, positive_xt: null, net_xt: null }] };
const base: XTAction = { event_index: 0, id: "a", player_id: 100, player: "Player A", team_id: 10,
  type: "Pass", period: 1, minute: 5, second: 0, successful: true, x: 10, y: 40, end_x: 110, end_y: 40, xt: .3 };
export const xtActionsFixture: XTAction[] = [base, { ...base, event_index: 1, id: "b", type: "Carry", xt: -.1 },
  { ...base, event_index: 2, id: "c", xt: 0 }, { ...base, event_index: 3, id: "d", end_x: null, xt: null }];
