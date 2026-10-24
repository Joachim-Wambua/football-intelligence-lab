import type { ReportSelection } from "@/lib/match-report";
import { xtModelFixture, xtPlayersFixture } from "./xt-fixtures";

export const reportSelection: ReportSelection = { matchId: 1, teamId: 10, competitionId: 9, seasonId: 281 };
export const reportTeam = { team_id: 10, team: "Team A", passing: { attempted: 3, completed: 2, completion_pct: 66.7 }, shots: 2, shot_goals: 1, recorded_xg: .3, shots_with_xg: 1 };
export const reportFixtures: Record<string, unknown> = {
  "/competitions": [{ competition_id: 9, season_id: 281, competition_name: "Bundesliga", season_name: "2023/24" }],
  "/matches?competition_id=9&season_id=281": [
    { match_id: 1, match_date: "2024-01-01", home_team: "Team A", away_team: "Team B", home_score: 1, away_score: 0 },
    { match_id: 2, match_date: "2024-01-08", home_team: "New A", away_team: "New B", home_score: null, away_score: null },
  ],
  "/matches/1/summary": { match_id: 1, event_count: 10, teams: [reportTeam, { ...reportTeam, team_id: 20, team: "Team B", shots: 0, shot_goals: 0, recorded_xg: null, shots_with_xg: 0 }] },
  "/matches/1/shots?team_id=10": [
    { match_id: 1, event_index: 0, team_id: 10, team: "Team A", player_id: 100, player: "Player A", period: 1, minute: 8, x: 110, y: 40, goal: true, xg: .3 },
    { match_id: 1, event_index: 1, team_id: 10, team: "Team A", player_id: null, player: null, period: null, minute: null, x: null, y: null, goal: false, xg: null },
  ],
  "/matches/1/teams/10/progressive-passing": { match_id: 1, team_id: 10, definition: { threshold_m: 10, pitch_length_m: 105, pitch_width_m: 68, goal_x: 120, goal_y: 40, comparison: "greater_than_or_equal" }, players: [
    { rank: 1, player_id: 100, player: "Player A", passes: 3, valid_geometry: 2, progressive_attempts: 2, completed_progressive: 1, progressive_pct: 66.7, net_progression_m: 17.5 },
  ] },
  "/matches/1/teams/10/insights": { match_id: 1, team_id: 10, xt_status: "available", observations: [
    { metric: "shots", definition: "Count of Shot events; all periods; excludes own-goal events.", value: 2, denominator: null, player_id: null, player: null, model_id: null },
    { metric: "experimental_positive_xt_leader", definition: "Sum of positive rated changes, not a rating.", value: .3, denominator: 3, player_id: 100, player: "Player A", model_id: "fixture-model" },
  ] },
  "/xt/model": xtModelFixture,
  "/matches/1/teams/10/xt/players": xtPlayersFixture,
};
