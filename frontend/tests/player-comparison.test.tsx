import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SWRConfig } from "swr";
import { expect, it, vi } from "vitest";
import { ComparisonBars, PlayerComparison } from "@/components/player-comparison";
import { PlayerCatalogue } from "@/components/player-intelligence";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { collectionQuery } from "@/lib/player-contracts";
import { comparisonCatalogue } from "./comparison-fixtures";
import { playerContext, playerProfileFixture } from "./player-fixtures";

const cataloguePath = `/player-intelligence/players?${collectionQuery(playerContext)}`;
function mockApi() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = url.split("/api/v1")[1];
    const value = path === cataloguePath ? comparisonCatalogue() : playerProfileFixture;
    return new Response(JSON.stringify(value));
  }));
}
function catalogue() {
  const cache = new Map();
  const wrapper = ({ children }: { children: React.ReactNode }) => <SWRConfig value={{ provider: () => cache }}>{children}</SWRConfig>;
  return render(<PlayerCatalogue context={playerContext}/>, { wrapper });
}

it("compares distinct provider IDs with explicit matched files, minutes and all positions", () => {
  render(<PlayerComparison catalogue={comparisonCatalogue()}/>);
  expect(screen.getByLabelText("First player")).toHaveValue("1");
  expect(screen.getByLabelText("Second player")).toHaveValue("2");
  expect(within(screen.getByLabelText("Second player")).queryByRole("option", { name: "Same name · ID 1" })).not.toBeInTheDocument();
  expect(screen.getByText(/Competition 9.*Season 281.*Selected match IDs: 1, 2/)).toBeInTheDocument();
  expect(screen.getByRole("article", { name: "Evidence for Same name · ID 1" })).toHaveTextContent("80.00");
  expect(screen.getByRole("article", { name: "Evidence for Same name · ID 2" })).toHaveTextContent("120.00");
  expect(screen.getByText(/All recorded positions: Center Midfield, Left Wing/)).toBeInTheDocument();
  expect(screen.getByText(/All recorded positions: Goalkeeper/)).toBeInTheDocument();
});

it("searches and changes either ID while enforcing distinct selections", async () => {
  render(<PlayerComparison catalogue={comparisonCatalogue()}/>);
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("First player"), "2");
  expect(screen.getByLabelText("Second player")).toHaveValue("1");
  await user.type(screen.getByLabelText("Search first player"), "Third");
  expect(screen.getByLabelText("First player")).toHaveValue("3");
  await user.type(screen.getByLabelText("Search second player"), "not found");
  expect(screen.getByText(/No matching distinct second player/)).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Evidence and exposure" })).not.toBeInTheDocument();
});

it("uses Python-provided totals and per90 rather than deriving rates in TypeScript", async () => {
  render(<PlayerComparison catalogue={comparisonCatalogue()}/>);
  const totals = screen.getByRole("region", { name: "Pass attempts numeric values" });
  expect(totals).toHaveTextContent("10.00");
  await userEvent.selectOptions(screen.getByLabelText("Comparison view"), "per90");
  expect(screen.getByRole("region", { name: "Pass attempts numeric values" })).toHaveTextContent("11.25");
  expect(screen.getByRole("region", { name: "Pass attempts numeric values" })).toHaveTextContent("15.00");
});

it("preserves signed xT, genuine zeros, focusable chart details and numeric alternatives", async () => {
  const { container } = render(<PlayerComparison catalogue={comparisonCatalogue()}/>);
  const negative = screen.getByRole("img", { name: "Same name · ID 1: -0.0200" });
  negative.focus(); expect(negative).toHaveFocus();
  await userEvent.tab();
  expect(screen.getByRole("img", { name: "Same name · ID 2: 0.0100" })).toHaveFocus();
  const chart = screen.getByRole("group", { name: /Experimental net xT estimate: side-by-side bars/ });
  expect(Number(chart.querySelector("rect")!.getAttribute("x"))).toBeLessThan(Number(chart.querySelector("line")!.getAttribute("x1")));
  expect(container.querySelectorAll("[data-zero=true]").length).toBeGreaterThan(0);
  expect(screen.getByRole("table", { name: "Experimental net xT estimate · totals" })).toHaveTextContent("-0.0200");
});

it("keeps partial estimate sums in labelled tables while withholding misleading bars", () => {
  render(<PlayerComparison catalogue={comparisonCatalogue()}/>);
  const region = screen.getByRole("region", { name: "Provider xG estimate numeric values" });
  expect(region).toHaveTextContent("0.4000");
  expect(region).toHaveTextContent("covered shots only");
  expect(region).toHaveTextContent("1/2 covered");
  const chart = screen.getByRole("group", { name: /Provider xG estimate: side-by-side bars/ });
  expect(chart.querySelector("[data-bar]")).toBeNull();
  expect(chart.querySelector("[data-zero]")).toBeNull();
  expect(within(chart).getAllByRole("img", { name: /Unavailable for chart/ })).toHaveLength(2);
});

it("displays null/zero-minute exposure without a zero-valued per90 placeholder", async () => {
  const data = comparisonCatalogue();
  data.players[1].aggregate.minutes = data.players[1].aggregate.known_minutes = 0;
  for (const row of Object.values(data.players[1].aggregate.comparison_evidence)) row.per90 = null;
  data.players[0].aggregate.minutes = null;
  render(<PlayerComparison catalogue={data}/>);
  expect(screen.getByRole("article", { name: "Evidence for Same name · ID 1" })).toHaveTextContent("Verified total minutes: Unavailable");
  expect(screen.getByRole("article", { name: "Evidence for Same name · ID 2" })).toHaveTextContent("Verified total minutes: 0.00");
  await userEvent.selectOptions(screen.getByLabelText("Comparison view"), "per90");
  const region = screen.getByRole("region", { name: "Pass attempts numeric values" });
  expect(region).toHaveTextContent("Unavailable");
});

it("shows useful empty/error states and does not refetch a second player's aggregate", async () => {
  mockApi(); catalogue();
  await screen.findByLabelText("Player identity");
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Compare players" }));
  await user.selectOptions(screen.getByLabelText("Second player"), "3");
  expect(globalThis.fetch).toHaveBeenCalledTimes(2); // Catalogue + the original profile only.
  expect(screen.getByLabelText("Second player")).toHaveValue("3");
});

it("clears comparison charts when a new collection is pending and ignores a late old response", async () => {
  mockApi(); const view = catalogue();
  await screen.findByLabelText("Player identity");
  await userEvent.click(screen.getByRole("button", { name: "Compare players" }));
  let finish!: (response: Response) => void;
  const pending = new Promise<Response>(resolve => { finish = resolve; });
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.includes("team_id=20")) {
      const current = comparisonCatalogue();
      current.context = { ...current.context, team_id: 20, requested_match_ids: [2], included_match_ids: [2] };
      current.players = [];
      return new Response(JSON.stringify(current));
    }
    return (await pending).clone();
  }));
  view.rerender(<PlayerCatalogue context={{ ...playerContext, matchIds: [2] }}/>);
  expect(screen.queryByRole("heading", { name: "Compare two players" })).not.toBeInTheDocument();
  expect(screen.getByText("Preparing bounded player collection…")).toBeInTheDocument();
  view.rerender(<PlayerCatalogue context={{ ...playerContext, teamId: 20, matchIds: [2] }}/>);
  await screen.findByText("No players match this selection.");
  await act(async () => { finish(new Response(JSON.stringify(comparisonCatalogue()))); });
  expect(screen.getByText("No players match this selection.")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Evidence and exposure" })).not.toBeInTheDocument();
});

it("handles fewer than two available identities", () => {
  const data = comparisonCatalogue(); data.players = data.players.slice(0, 1);
  render(<PlayerComparison catalogue={data}/>);
  expect(screen.getByText(/At least two distinct player IDs/)).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("preserves Light, Dark and System controls while exposing charts without color-only labels", async () => {
  render(<ThemeProvider><ThemeSwitcher/><PlayerComparison catalogue={comparisonCatalogue()}/></ThemeProvider>);
  const user = userEvent.setup();
  for (const mode of ["Dark", "Light", "System"]) {
    await user.click(screen.getByRole("button", { name: mode }));
    expect(localStorage.getItem("fil-theme")).toBe(mode.toLowerCase());
    expect(screen.getByRole("img", { name: "Same name · ID 1: -0.0200" })).toBeInTheDocument();
  }
  expect(screen.getAllByText(/Solid and outlined bars/).length).toBeGreaterThan(0);
});


it("does not round a tiny signed model change into a displayed zero", () => {
  render(<ComparisonBars label="Tiny experimental delta" names={["A", "B"]} values={[-.00000001, 0]} estimated/>);
  expect(screen.getByRole("img", { name: "A: -1.00e-8" })).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "B: 0.0000" })).toBeInTheDocument();
});
