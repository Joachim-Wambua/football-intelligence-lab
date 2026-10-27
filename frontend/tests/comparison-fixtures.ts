import type { PlayerCatalogueData } from "@/lib/player-contracts";
import { playerCatalogueFixture } from "./player-fixtures";

/** Fixed server-owned values: tests must not compute football rates in the UI. */
export function comparisonCatalogue(): PlayerCatalogueData {
  const catalogue = structuredClone(playerCatalogueFixture);
  catalogue.context.lineups_unavailable_match_ids = [];
  // The base fixture intentionally shares an aggregate; isolate each identity.
  catalogue.players = catalogue.players.map(player => structuredClone(player));
  catalogue.players.forEach((player, index) => {
    player.positions = index === 0 ? ["Center Midfield", "Left Wing"] : ["Goalkeeper"];
    const aggregate = player.aggregate;
    aggregate.minutes = aggregate.known_minutes = index === 0 ? 80 : 120;
    aggregate.minutes_covered_matches = 2;
    aggregate.per90_match_ids = [1, 2];
    aggregate.statistics.passes = index === 0 ? 10 : 20;
    aggregate.statistics.goals = 0;
    aggregate.statistics.xt_net = index === 0 ? -.02 : .01;
    aggregate.statistics.xt_attempted_actions = aggregate.statistics.xt_rated_actions = index === 0 ? 10 : 20;
    aggregate.per90.passes = index === 0 ? 11.25 : 15;
    aggregate.per90.xt_net = index === 0 ? -.0225 : .0075;
    aggregate.comparison_evidence.passes = { ...aggregate.comparison_evidence.passes, total: aggregate.statistics.passes,
      chart_total: aggregate.statistics.passes, per90: aggregate.per90.passes };
    aggregate.comparison_evidence.goals = { ...aggregate.comparison_evidence.goals, total: 0, chart_total: 0, per90: 0 };
    aggregate.comparison_evidence.xt_net = { ...aggregate.comparison_evidence.xt_net,
      total: aggregate.statistics.xt_net, chart_total: aggregate.statistics.xt_net, per90: aggregate.per90.xt_net,
      status: "complete", coverage_count: aggregate.statistics.xt_rated_actions, coverage_total: aggregate.statistics.xt_attempted_actions };
  });
  catalogue.players.push({ ...structuredClone(catalogue.players[0]), player_id: 3, player: "Third identity", aliases: ["Third identity"] });
  return catalogue;
}
