import { z } from "zod";

const number = z.number().finite();
const id = number.int().positive();
export const competitionSchema = z.object({ competition_id: id, season_id: id, competition_name: z.string(), season_name: z.string(), country_name: z.string().nullable().optional(), competition_gender: z.string().nullable().optional() });
export const matchSchema = z.object({ match_id: id, match_date: z.string(), home_team: z.string(), away_team: z.string(), home_score: number.nullable().optional(), away_score: number.nullable().optional() });
export const teamSchema = z.object({ team_id: id, team: z.string(), passing: z.object({ attempted: number, completed: number, completion_pct: number }), shots: number, shot_goals: number, recorded_xg: number.nullable(), shots_with_xg: number });
export const summarySchema = z.object({ match_id: id, event_count: number, teams: z.array(teamSchema) });
export const playerSchema = z.object({ player_id: id, player: z.string(), passes: number, completed_passes: number, pass_completion_pct: number, shots: number, goals: number, xg: number.nullable(), successful_dribbles: number, successful_interceptions: number });
export const passSchema = z.object({ id: z.string().nullable().optional(), minute: number.nullable().optional(), second: number.nullable().optional(), period: number.nullable().optional(), completed: z.boolean(), x: number.nullable(), y: number.nullable(), end_x: number.nullable(), end_y: number.nullable(),
  valid_geometry: z.boolean(), start_distance_sb: number.nullable(), end_distance_sb: number.nullable(),
  start_distance_m: number.nullable(), end_distance_m: number.nullable(), progression_sb: number.nullable(), progression_m: number.nullable(),
  progressive: z.boolean(), completed_progressive: z.boolean(),
});
export const progressionDefinitionSchema = z.object({ threshold_m: number.positive(), pitch_length_m: number.positive(), pitch_width_m: number.positive(), goal_x: z.literal(120), goal_y: z.literal(40), comparison: z.literal("greater_than_or_equal") });
export const playerProgressionSchema = z.object({ rank: id, player_id: id, player: z.string(), passes: number.int().nonnegative(), valid_geometry: number.int().nonnegative(), progressive_attempts: number.int().nonnegative(), completed_progressive: number.int().nonnegative(), progressive_pct: number, net_progression_m: number.nullable() });
export const teamProgressionSchema = z.object({ match_id: id, team_id: id, definition: progressionDefinitionSchema, players: z.array(playerProgressionSchema) });
export type Competition = z.infer<typeof competitionSchema>;
export type Match = z.infer<typeof matchSchema>;
export type Team = z.infer<typeof teamSchema>;
export type Player = z.infer<typeof playerSchema>;
export type Pass = z.infer<typeof passSchema>;
export type TeamProgression = z.infer<typeof teamProgressionSchema>;
