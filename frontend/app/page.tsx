import { Dashboard } from "@/components/dashboard";
import { readMatchSelection } from "@/lib/match-navigation";

/** Route values are validated before client state restores provider membership. */
export default async function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const query = await searchParams;
  // Raw route identity also resets defaults when two different invalid URLs normalize alike.
  return <Dashboard initialSelection={readMatchSelection(query)} navigationKey={JSON.stringify(query)}/>;
}
