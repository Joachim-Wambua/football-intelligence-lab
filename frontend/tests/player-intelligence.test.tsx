import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SWRConfig } from "swr";
import { expect, it, vi } from "vitest";
import { PlayerCatalogue, PlayerIntelligence, PlayerProfileView } from "@/components/player-intelligence";
import { Shell } from "@/components/shell";
import { ThemeProvider } from "@/components/theme-provider";
import { collectionQuery, playerCatalogueSchema } from "@/lib/player-contracts";
import { playerCatalogueFixture, playerProfileFixture, playerContext } from "./player-fixtures";

const base = `/player-intelligence/players`;
const query = collectionQuery(playerContext);
function mockApi(overrides: Record<string, unknown> = {}, failures: string[] = []) {
  const data: Record<string, unknown> = { [`${base}?${query}`]: playerCatalogueFixture,
    [`${base}/1?${query}`]: playerProfileFixture,
    [`${base}/2?${query}`]: { ...playerProfileFixture, identity: { ...playerProfileFixture.identity, player_id: 2, player: "Second identity" } }, ...overrides };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = url.split("/api/v1")[1];
    return new Response(JSON.stringify(data[path] ?? {}), { status: failures.includes(path) ? 502 : path in data ? 200 : 404 });
  }));
}
function catalogue() {
  const cache = new Map();
  const wrapper = ({ children }: { children: React.ReactNode }) => <SWRConfig value={{ provider: () => cache, dedupingInterval: 0 }}>{children}</SWRConfig>;
  return render(<PlayerCatalogue context={playerContext}/>, { wrapper });
}

it("shows ID-distinct players, qualified minutes, partial xG and links to exact match context", async () => {
  mockApi(); catalogue();
  expect(await screen.findByRole("heading", { name: "Same name" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Same name · ID 1" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Same name · ID 2" })).toBeInTheDocument();
  expect(screen.getByText(/90.00 known elapsed pitch minutes/)).toBeInTheDocument();
  expect(screen.getByText(/Provider xG coverage: 1 \/ 2 shots/)).toBeInTheDocument();
  expect(screen.getAllByText(/not a full league season/).length).toBeGreaterThan(0);
  expect(screen.getAllByRole("link", { name: /A vs B/ })[1]).toHaveAttribute("href", "/?competition_id=9&season_id=281&match_id=2&team_id=10");
  expect(screen.getByRole("region", { name: "Player aggregate statistics" })).toHaveTextContent("Unavailable");
  expect(screen.getAllByText(/Model ID: frozen-model/).length).toBeGreaterThan(0);
});

it("searches provider IDs and switches identity without retaining the old profile", async () => {
  mockApi(); catalogue();
  await screen.findByRole("heading", { name: "Same name" });
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Player identity"), "2");
  expect(await screen.findByRole("heading", { name: "Second identity" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Same name" })).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("Search player name or provider ID"), "not present");
  expect(screen.getByText("No players match this selection.")).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Player match contributions" })).not.toBeInTheDocument();
});

it("isolates delayed profile responses when collections change", async () => {
  mockApi();
  const fetchCurrent = globalThis.fetch;
  let finish!: (response: Response) => void;
  const pending = new Promise<Response>(resolve => { finish = resolve; });
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => url.includes(`${base}/1?`) ? pending : fetchCurrent(url, init)));
  const view = catalogue();
  await screen.findByLabelText("Player identity");
  await waitFor(() => expect(screen.getByText("Loading player contributions…")).toBeInTheDocument());
  view.rerender(<PlayerCatalogue context={{ ...playerContext, matchIds: [2] }}/>);
  await screen.findByRole("alert");
  await act(async () => { finish(new Response(JSON.stringify(playerProfileFixture))); });
  expect(screen.queryByRole("heading", { name: "Same name" })).not.toBeInTheDocument();
});

it("retains explicit empty and retryable error states", async () => {
  mockApi({}, [`${base}?${query}`]); catalogue();
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  mockApi({ [`${base}?${query}`]: { ...playerCatalogueFixture, players: [] } });
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("No players match this selection.")).toBeInTheDocument();
});

it("presents unused/unknown appearances and unavailable xT without fabricated rates", () => {
  const profile = structuredClone(playerProfileFixture);
  profile.identity.aggregate.appearances = 0;
  profile.identity.aggregate.unknown_appearances = 1;
  profile.identity.aggregate.minutes = 0;
  profile.model.status = "unavailable";
  profile.model.model_id = null;
  profile.matches[0].minutes = 0; profile.matches[0].appeared = false;
  profile.matches[0].minutes_status = "unused_substitute";
  profile.matches[1].appeared = null;
  render(<PlayerProfileView profile={profile}/>);
  expect(screen.getByText("Did not appear")).toBeInTheDocument();
  expect(screen.getByText("Unknown")).toBeInTheDocument();
  expect(screen.getByText(/0.00.*unused substitute/)).toBeInTheDocument();
  expect(screen.getByText(/1 unknown appearances/)).toBeInTheDocument();
});

it("supports module navigation with accessible mobile state and theme controls", async () => {
  render(<ThemeProvider><Shell><p>Player page</p></Shell></ThemeProvider>);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Menu" }));
  expect(screen.getByRole("link", { name: "Player Intelligence" })).toHaveAttribute("href", "/players");
  const link = screen.getByRole("link", { name: "Player Intelligence" });
  link.addEventListener("click", event => event.preventDefault());
  await user.click(link);
  expect(screen.getByRole("button", { name: "Menu" })).toHaveAttribute("aria-expanded", "false");
  await user.click(screen.getByRole("button", { name: "Dark" }));
  expect(localStorage.getItem("fil-theme")).toBe("dark");
});

it("caps the explicit applied collection at five fixtures", async () => {
  const matches = Array.from({ length: 7 }, (_, index) => ({ match_id: index + 1, match_date: `2024-01-0${index+1}`, home_team: "A", away_team: "B" }));
  const team = { team_id: 10, team: "A", passing: { attempted: 1, completed: 1, completion_pct: 100 }, shots: 0, shot_goals: 0, recorded_xg: null, shots_with_xg: 0 };
  mockApi({ "/competitions": [{ competition_id: 9, season_id: 281, competition_name: "Bundesliga", season_name: "2023/24" }],
    "/matches?competition_id=9&season_id=281": matches, "/matches/1/summary": { match_id: 1, event_count: 1, teams: [team] } });
  render(<SWRConfig value={{ provider: () => new Map() }}><PlayerIntelligence/></SWRConfig>);
  const checkboxes = await screen.findAllByRole("checkbox");
  for (const box of checkboxes.slice(1, 5)) await userEvent.click(box);
  expect(checkboxes[5]).toBeDisabled();
  expect(checkboxes[6]).toBeDisabled();
  expect(screen.getByText(/5\/5 selected/)).toBeInTheDocument();
});

it("validates minute contracts and canonical collection identities", () => {
  expect(collectionQuery({ ...playerContext, matchIds: [2, 1] })).toBe(query);
  expect(playerCatalogueSchema.safeParse({ ...playerCatalogueFixture, players: [{ ...playerProfileFixture.identity,
    aggregate: { ...playerProfileFixture.identity.aggregate, minutes: -1 } }] }).success).toBe(false);
});

it("rejects a shape-valid catalogue from another team context", async () => {
  mockApi({ [`${base}?${query}`]: { ...playerCatalogueFixture, context: { ...playerCatalogueFixture.context, team_id: 20 } } });
  catalogue();
  expect(await screen.findByRole("alert")).toHaveTextContent("does not match the selected collection");
  expect(screen.queryByLabelText("Player identity")).not.toBeInTheDocument();
});
