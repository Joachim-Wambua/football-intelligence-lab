import { Dashboard } from "@/components/dashboard";
import { positiveReportId } from "@/lib/match-report";

/** Deep links from Player Intelligence restore match/team selection by ID. */
export default async function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const query = await searchParams;
  return <Dashboard initialSelection={{ competitionId: positiveReportId(query.competition_id) ?? undefined,
    seasonId: positiveReportId(query.season_id) ?? undefined, matchId: positiveReportId(query.match_id) ?? undefined,
    teamId: positiveReportId(query.team_id) ?? undefined }}/>;
}
