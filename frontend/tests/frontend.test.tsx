import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToString } from "react-dom/server";
import { SWRConfig } from "swr";
import { describe, it, expect, vi } from "vitest";
import { z } from "zod";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { PassingPitch } from "@/components/charts";
import { Shell } from "@/components/shell";
import { Dashboard } from "@/components/dashboard";
import { apiGet } from "@/lib/api";
import type { Pass } from "@/lib/contracts";
import { xtModelFixture, xtPlayersFixture } from "./xt-fixtures";

const team = { team_id: 10, team: "A", passing: { attempted: 3, completed: 2, completion_pct: 66.7 }, shots: 2, shot_goals: 1, recorded_xg: null, shots_with_xg: 0 };
const player = { player_id: 100, player: "Player A", passes: 3, completed_passes: 2, pass_completion_pct: 66.7, shots: 2, goals: 1, xg: null, successful_dribbles: 1, successful_interceptions: 0 };
const pass: Pass = { id: "p", completed: true, x: 10, y: 20, end_x: 30, end_y: 40,
  valid_geometry: true, start_distance_sb: 110, end_distance_sb: 90, start_distance_m: 96.25, end_distance_m: 78.75,
  progression_sb: 20, progression_m: 17.5, progressive: true, completed_progressive: true };
const progression = { match_id: 1, team_id: 10, definition: { threshold_m: 10, pitch_length_m: 105, pitch_width_m: 68, goal_x: 120, goal_y: 40, comparison: "greater_than_or_equal" },
  players: [{ rank: 1, player_id: 100, player: "Player A", passes: 3, valid_geometry: 2, progressive_attempts: 2, completed_progressive: 1, progressive_pct: 66.7, net_progression_m: 17.5 }] };
const fixtures: Record<string, unknown> = {
  "/xt/model": xtModelFixture,
  "/matches/1/teams/10/xt/players": xtPlayersFixture,
  "/competitions": [{ competition_id: 9, season_id: 281, competition_name: "Bundesliga", season_name: "2023/24" }],
  "/matches?competition_id=9&season_id=281": [{ match_id: 1, match_date: "2024-01-01", home_team: "A", away_team: "B", home_score: 1, away_score: 0 }],
  "/matches/1/summary": { match_id: 1, event_count: 20, teams: [team] },
  "/matches/1/teams/10/players": [player, { ...player, player_id: 101, player: "Player B" }],
  "/matches/1/teams/10/progressive-passing": progression,
  "/matches/1/players/100/passes?threshold_m=10": [pass],
  "/matches/1/players/101/passes?threshold_m=10": [],
};
function mockApi() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(fixtures[url.split("/api/v1")[1]]), { status: 200 })));
}
function dashboard() {
  return render(<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}><Dashboard/></SWRConfig>);
}

describe("theme behavior", () => {
  it("renders hydration-safe disabled controls on the server", () => {
    const html = renderToString(<ThemeProvider><ThemeSwitcher/></ThemeProvider>);
    expect(html).toContain("disabled");
    expect(html).not.toContain('aria-pressed="true"');
  });
  it("follows system by default and persists explicit overrides", async () => {
    const user = userEvent.setup();
    const first = render(<ThemeProvider><ThemeSwitcher/></ThemeProvider>);
    expect(await screen.findByRole("button", { name: "System" })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(document.documentElement).toHaveClass("dark"));
    await user.click(screen.getByRole("button", { name: "Light" }));
    expect(localStorage.getItem("fil-theme")).toBe("light");
    expect(document.documentElement).toHaveClass("light");
    first.unmount();
    render(<ThemeProvider><ThemeSwitcher/></ThemeProvider>);
    expect(await screen.findByRole("button", { name: "Light" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Dark" }));
    expect(localStorage.getItem("fil-theme")).toBe("dark");
    await user.click(screen.getByRole("button", { name: "System" }));
    expect(localStorage.getItem("fil-theme")).toBe("system");
  });
});

it("exposes mobile navigation state and closes it on navigation", async () => {
  const user = userEvent.setup();
  render(<ThemeProvider><Shell><p>Workspace content</p></Shell></ThemeProvider>);
  await user.click(screen.getByRole("button", { name: "Menu" }));
  expect(screen.getByRole("button", { name: "Close" })).toHaveAttribute("aria-expanded", "true");
  await user.click(screen.getByRole("link", { name: /Player comparison/ }));
  expect(screen.getByRole("button", { name: "Menu" })).toHaveAttribute("aria-expanded", "false");
});

it("renders solid/dashed pass outcomes and omits missing coordinates", () => {
  const { container } = render(<PassingPitch player="Player A" passes={[pass, { ...pass, id: "q", completed: false }, { ...pass, x: null }]}/>);
  expect(screen.getByRole("group", { name: /Player A passing map/ })).toBeInTheDocument();
  expect(container.querySelectorAll("line[data-pass]")).toHaveLength(2);
  expect(container.querySelector("line[stroke-dasharray]")).toBeTruthy();
  expect(screen.getByText(/1 passes omitted/)).toBeInTheDocument();
});

it("loads API metrics without replacing null xG and switches player passes", async () => {
  mockApi();
  const user = userEvent.setup();
  dashboard();
  expect(screen.getByRole("status")).toHaveTextContent("Loading available competitions");
  expect(await screen.findByRole("group", { name: /Player A passing map/ })).toBeInTheDocument();
  expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
  expect(screen.getByRole("table", { name: /Player performance/ })).toHaveTextContent("66.7%");
  expect(screen.getByRole("link", { name: "Open shareable match report" })).toHaveAttribute("href", "/reports/1?competition_id=9&season_id=281&team_id=10");
  await user.selectOptions(screen.getByLabelText("Player"), "101");
  expect(await screen.findByText("No passes recorded for this player.")).toBeInTheDocument();
});

it("shows an API failure and retries successfully", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 502 })));
  dashboard();
  expect(await screen.findByRole("alert")).toHaveTextContent("data provider is temporarily unavailable");
  mockApi();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("heading", { name: "Read the game." })).toBeInTheDocument();
});

it("rejects invalid API contracts and network failures", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"count":null}')));
  await expect(apiGet("/test", z.object({ count: z.number() }))).rejects.toThrow("expected contract");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  await expect(apiGet("/test", z.array(z.string()))).rejects.toThrow("Cannot reach the API");
});

it("clears match and player content when a different season has no matches", async () => {
  const data = { ...fixtures, "/competitions": [
    ...(fixtures["/competitions"] as object[]),
    { competition_id: 9, season_id: 282, competition_name: "Bundesliga", season_name: "2024/25" },
  ], "/matches?competition_id=9&season_id=282": [] };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(data[url.split("/api/v1")[1] as keyof typeof data]))));
  dashboard();
  await screen.findByRole("group", { name: /Player A passing map/ });
  await userEvent.selectOptions(screen.getByLabelText("Competition and season"), "9:282");
  expect(await screen.findByRole("heading", { name: "No matches available" })).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("group", { name: /passing map/ })).not.toBeInTheDocument();
});
