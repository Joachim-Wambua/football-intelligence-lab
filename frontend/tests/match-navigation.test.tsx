import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SWRConfig } from "swr";
import { expect, it, vi } from "vitest";
import MatchPage from "@/app/page";
import { PlayerProfileView } from "@/components/player-intelligence";
import { readMatchSelection } from "@/lib/match-navigation";
import { playerProfileFixture } from "./player-fixtures";

type Query = Record<string, string | string[] | undefined>;
const team = (id: number, name: string) => ({ team_id: id, team: name, passing: { attempted: 4, completed: 3, completion_pct: 75 }, shots: 2, shot_goals: 1, recorded_xg: .3, shots_with_xg: 1 });
const match = (id: number, home: string, away: string) => ({ match_id: id, match_date: "2024-01-01", home_team: home, away_team: away });
const linked: Query = { competition_id: "43", season_id: "3", match_id: "4", team_id: "40" };
const data: Record<string, unknown> = {
  "/competitions": [
    { competition_id: 9, season_id: 281, competition_name: "Bundesliga", season_name: "2023/24" },
    { competition_id: 43, season_id: 3, competition_name: "World Cup", season_name: "2018" },
    { competition_id: 9, season_id: 282, competition_name: "Bundesliga", season_name: "2024/25" }],
  "/matches?competition_id=9&season_id=281": [match(1, "A", "B"), match(2, "C", "D")],
  "/matches?competition_id=43&season_id=3": [match(3, "X", "V"), match(4, "U", "V")],
  "/matches?competition_id=9&season_id=282": [],
  "/matches/1/summary": { match_id: 1, event_count: 20, teams: [team(10, "A"), team(40, "B")] },
  "/matches/2/summary": { match_id: 2, event_count: 20, teams: [team(20, "C"), team(10, "D")] },
  "/matches/3/summary": { match_id: 3, event_count: 20, teams: [team(50, "X"), team(40, "V")] },
  "/matches/4/summary": { match_id: 4, event_count: 20, teams: [team(30, "U"), team(40, "V")] },
};
function mockApi() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = url.split("/api/v1")[1];
    return new Response(JSON.stringify(data[path] ?? {}), { status: path in data ? 200 : 404 });
  }));
}
async function destination(query: Query) {
  const cache = new Map();
  const wrapper = ({ children }: { children: React.ReactNode }) => <SWRConfig value={{ provider: () => cache }}>{children}</SWRConfig>;
  return render(await MatchPage({ searchParams: Promise.resolve(query) }), { wrapper });
}
async function expectSelection(competition: string, match: string, team: string) {
  await waitFor(() => {
    expect(screen.getByLabelText("Competition and season")).toHaveValue(competition);
    expect(screen.getByLabelText("Match")).toHaveValue(match);
    expect(screen.getByLabelText("Team")).toHaveValue(team);
  });
}

it("follows a real Player Intelligence contribution link into the actual destination selection", async () => {
  mockApi();
  const profile = render(<PlayerProfileView profile={playerProfileFixture}/>);
  const href = screen.getAllByRole("link", { name: /A vs B/ })[1].getAttribute("href")!;
  profile.unmount();
  await destination(Object.fromEntries(new URL(href, "http://localhost").searchParams));
  await expectSelection("9:281", "2", "10");
  await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/matches/2/teams/10/players"), expect.anything()));
});

it("restores a nondefault competition/season, nonfirst match and nonfirst team through the route", async () => {
  mockApi(); await destination(linked);
  await expectSelection("43:3", "4", "40");
  await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/matches/4/teams/40/players"), expect.anything()));
});

it.each([
  [{}, "9:281", "1", "10"],
  [{ ...linked, competition_id: "999" }, "9:281", "1", "10"],
  [{ ...linked, season_id: "999" }, "9:281", "1", "10"],
  [{ ...linked, match_id: "999" }, "43:3", "3", "50"],
  [{ ...linked, team_id: "999" }, "43:3", "4", "30"],
  [{ ...linked, season_id: undefined }, "9:281", "1", "10"],
  [{ ...linked, competition_id: ["43", "9"] }, "9:281", "1", "10"],
  [{ ...linked, match_id: "1.5" }, "43:3", "3", "50"],
] as [Query, string, string, string][])("uses context-safe defaults for URL %j", async (query, competition, match, team) => {
  mockApi(); await destination(query); await expectSelection(competition, match, team);
});

it("resets local state on subsequent URL navigation instead of ignoring new page props", async () => {
  mockApi(); const view = await destination(linked);
  await expectSelection("43:3", "4", "40");
  view.rerender(await MatchPage({ searchParams: Promise.resolve({ competition_id: "9", season_id: "281", match_id: "2", team_id: "10" }) }));
  await expectSelection("9:281", "2", "10");
});

it("does not carry URL team state into a manually selected match or season", async () => {
  mockApi(); await destination(linked);
  await expectSelection("43:3", "4", "40");
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Match"), "3");
  await expectSelection("43:3", "3", "50");
  await user.selectOptions(screen.getByLabelText("Competition and season"), "9:281");
  await expectSelection("9:281", "1", "10");
});

it("ignores an old delayed summary after URL context changes", async () => {
  mockApi(); const currentFetch = globalThis.fetch;
  let finish!: (value: Response) => void;
  const pending = new Promise<Response>(resolve => { finish = resolve; });
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => url.endsWith("/matches/4/summary") ? pending : currentFetch(url, init)));
  const view = await destination(linked);
  await screen.findByLabelText("Match");
  view.rerender(await MatchPage({ searchParams: Promise.resolve({ competition_id: "9", season_id: "281", match_id: "2", team_id: "10" }) }));
  await expectSelection("9:281", "2", "10");
  await act(async () => { finish(new Response(JSON.stringify(data["/matches/4/summary"]))); });
  await expectSelection("9:281", "2", "10");
});

it("rejects unsafe IDs and repeated child IDs without dropping valid ancestors", () => {
  for (const value of ["0", "-1", "1e3", "9007199254740992", "NaN", ["4", "3"]]) {
    expect(readMatchSelection({ ...linked, match_id: value })).toEqual({ competitionId: 43, seasonId: 3 });
  }
  expect(readMatchSelection({ ...linked, team_id: ["40", "30"] })).toEqual({ competitionId: 43, seasonId: 3, matchId: 4, teamId: undefined });
});


it("keeps an explicitly available empty season rather than selecting another season's match", async () => {
  mockApi(); await destination({ ...linked, competition_id: "9", season_id: "282" });
  expect(await screen.findByRole("heading", { name: "No matches available" })).toBeInTheDocument();
  expect(screen.getByLabelText("Competition and season")).toHaveValue("9:282");
  expect(screen.queryByLabelText("Match")).not.toBeInTheDocument();
});


it("resets sensible defaults for a new invalid URL even after manual selection", async () => {
  mockApi(); const view = await destination({});
  await expectSelection("9:281", "1", "10");
  await userEvent.selectOptions(screen.getByLabelText("Competition and season"), "43:3");
  await expectSelection("43:3", "3", "50");
  view.rerender(await MatchPage({ searchParams: Promise.resolve({ ...linked, competition_id: "bad" }) }));
  await expectSelection("9:281", "1", "10");
});
