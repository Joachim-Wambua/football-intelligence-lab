import { notFound } from "next/navigation";
import { MatchReport } from "@/components/match-report";
import { positiveReportId } from "@/lib/match-report";

export const metadata = { title: "Match report | Football Intelligence Lab" };

/** Validate shared URL context before making any provider requests. */
export default async function ReportPage({ params, searchParams }: {
  params: Promise<{ matchId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const route = await params;
  const query = await searchParams;
  const matchId = positiveReportId(route.matchId);
  const competitionId = positiveReportId(query.competition_id);
  const seasonId = positiveReportId(query.season_id);
  const teamId = positiveReportId(query.team_id);
  if (!matchId || !competitionId || !seasonId || !teamId) notFound();
  return <MatchReport selection={{ matchId, competitionId, seasonId, teamId }}/>;
}
