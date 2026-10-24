import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SWRConfig } from "swr";
import { vi, it, expect } from "vitest";
import { ShotMap, MatchWorkspace } from "@/components/match-workspace";
import { Shell } from "@/components/shell";
import type { Shot } from "@/lib/contracts";
const shot: Shot = { match_id: 1, event_index: 1, team_id: 10, team: "A", player_id: 100, player: "Ada", period: 1, minute: 8, x: 110, y: 40, goal: true, xg: .3 };
it("distinguishes goals, exposes keyboard details and filters without hiding missing events", async () => {
  const user = userEvent.setup();
  render(<ShotMap shots={[shot, { ...shot, event_index: 2, player_id: 101, player: "Bea", x: null, goal: false, xg: null }]}/>);
  expect(screen.getByText("G")).toBeInTheDocument();
  const marker = within(screen.getByRole("group", { name: "Interactive shot map, attacking right" })).getByRole("button", { name: /Ada.*Goal/ });
  marker.focus();
  await user.keyboard("{Enter}");
  expect(screen.getByRole("status")).toHaveTextContent("xG 0.3");
  await user.keyboard("{Escape}");
  expect(screen.getByRole("status")).toHaveTextContent("Focus or select");
  await user.selectOptions(screen.getByLabelText("Shot player"), "101");
  expect(screen.queryByRole("button", { name: /Ada.*Goal/ })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Bea.*unavailable/ })).toBeInTheDocument();
  expect(screen.getByText(/1 shots omitted/)).toBeInTheDocument();
});
it("handles empty shots and mobile navigation including xT", async () => {
  const user = userEvent.setup();
  render(<Shell><ShotMap shots={[]}/></Shell>);
  expect(screen.getByText("No shots for this selection.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Menu" }));
  expect(screen.getByRole("button", { name: "Close" })).toHaveAttribute("aria-expanded", "true");
  await user.click(screen.getByRole("link", { name: /Expected Threat/ }));
  expect(screen.getByRole("button", { name: "Menu" })).toHaveAttribute("aria-expanded", "false");
});
it("clears old evidence while a new match/team request is pending", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.includes("/matches/2/")) return new Promise<Response>(() => {});
    return new Response(JSON.stringify(url.includes("/shots?") ? [shot] : { match_id: 1, team_id: 10, observations: [], xt_status: "unavailable" }));
  }));
  const wrapper = ({ children }: { children: React.ReactNode }) => <SWRConfig value={{ provider: () => new Map() }}>{children}</SWRConfig>;
  const view = render(<MatchWorkspace matchId={1} teamId={10}/>, { wrapper });
  expect((await screen.findAllByRole("button", { name: /Ada.*Goal/ })).length).toBe(2);
  view.rerender(<MatchWorkspace matchId={2} teamId={20}/>);
  expect(screen.queryByRole("button", { name: /Ada.*Goal/ })).not.toBeInTheDocument();
  expect(screen.getByText("Loading shot events…")).toBeInTheDocument();
});
it("shows retryable errors and recovers without rendering fabricated events", async () => {
  const user = userEvent.setup();
  let failing = true;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (failing) return new Response("{}", { status: 502 });
    return new Response(JSON.stringify(url.includes("/shots?") ? [] : { match_id: 1, team_id: 10, observations: [], xt_status: "unavailable" }));
  }));
  render(<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}><MatchWorkspace matchId={1} teamId={10}/></SWRConfig>);
  expect(await screen.findAllByRole("alert")).toHaveLength(2);
  failing = false;
  for (const button of screen.getAllByRole("button", { name: "Try again" })) await user.click(button);
  expect(await screen.findByText("No shots for this selection.")).toBeInTheDocument();
  expect(screen.queryAllByRole("alert")).toHaveLength(0);
});
