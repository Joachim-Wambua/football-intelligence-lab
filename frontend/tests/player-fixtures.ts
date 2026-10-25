import type { PlayerProfile } from "@/lib/player-contracts";
export const playerContext = { competitionId: 9, seasonId: 281, teamId: 10, matchIds: [1, 2] };
const statistics = { passes: 10, completed_passes: 8, completed_progressive_passes: 2, progressive_valid_geometry: 9,
  shots: 2, goals: 1, shots_with_xg: 1, xg: .4, successful_dribbles: 1, successful_interceptions: 2,
  xt_positive: .03, xt_net: -.01, xt_rated_actions: 8, xt_attempted_actions: 12 };
const aggregate = { appearances: 2, unknown_appearances: 0, minutes: null, known_minutes: 90, minutes_covered_matches: 1,
  statistics, per90: { passes: null, completed_passes: null, completed_progressive_passes: null, shots: null, goals: null,
    xg: null, successful_dribbles: null, successful_interceptions: null, xt_positive: null, xt_net: null }, per90_match_ids: [] };
export const playerProfileFixture: PlayerProfile = {
  context: { competition_id: 9, season_id: 281, team_id: 10, requested_match_ids: [1, 2], included_match_ids: [1, 2],
    failed_matches: [], lineups_unavailable_match_ids: [2], available_catalogue_matches: 34,
    sample_label: "Explicit selected-match collection; not a full league season" },
  definitions: { minutes: "Explicit Starting XI, substitutions, dismissals and Half Ends; no first/last touch inference.",
    per90: "90 * metric / valid elapsed minutes for the same included matches.", xg: "Available values only; covered shots / all shots." },
  model: { status: "available", model_id: "frozen-model", training_matches: 6, held_out_matches: 2, shot_zones: 26, total_zones: 192,
    limitations: "Experimental, small Leverkusen sample; not player ratings or league-wide comparisons." },
  identity: { player_id: 1, player: "Same name", aliases: ["Same name"], team_id: 10, team: "A", positions: ["Center Midfield"], aggregate },
  matches: [1, 2].map(matchId => ({ match_id: matchId, match_date: `2024-01-0${matchId}`, home_team: "A", away_team: "B", team_id: 10, team: "A",
    positions: ["Center Midfield"], position_history: [], minutes: matchId === 1 ? 90 : null, appeared: true,
    minutes_status: matchId === 1 ? "verified" : "lineups_unavailable", minutes_provenance: "Provider lifecycle, added time included; intervals excluded.", statistics,
    per90: aggregate.per90, model_id: "frozen-model" })),
};
export const playerCatalogueFixture = { context: playerProfileFixture.context, definitions: playerProfileFixture.definitions, model: playerProfileFixture.model,
  players: [playerProfileFixture.identity, { ...playerProfileFixture.identity, player_id: 2 }] };
