import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SWRConfig } from "swr";
import { expect, it, vi } from "vitest";
import { PassingPitch } from "@/components/charts";
import { ProgressivePassing } from "@/components/progressive-passing";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { filterPasses } from "@/lib/pass-filters";
import { passSchema, type Pass, type Player } from "@/lib/contracts";

const base: Pass = { id: "a", minute: 2, second: 5, period: 1, x: 40, y: 40, end_x: 60, end_y: 40,
  completed: true, valid_geometry: true, start_distance_sb: 80, end_distance_sb: 60,
  start_distance_m: 70, end_distance_m: 52.5, progression_sb: 20, progression_m: 17.5,
  progressive: true, completed_progressive: true };
const passes: Pass[] = [base,
  { ...base, id: "b", completed: false, completed_progressive: false },
  { ...base, id: "c", progressive: false, completed_progressive: false, progression_m: -17.5 },
  { ...base, id: "d", completed: false, progressive: false, completed_progressive: false, progression_m: 0 },
  { ...base, id: "e", x: null, valid_geometry: false, progressive: false, completed_progressive: false, progression_m: null },
];

it("filters only API-owned flags without calculating progression", () => {
  expect(filterPasses(passes, "all")).toHaveLength(5);
  expect(filterPasses(passes, "completed").map(p => p.id)).toEqual(["a", "c", "e"]);
  expect(filterPasses(passes, "unsuccessful").map(p => p.id)).toEqual(["b", "d"]);
  expect(filterPasses(passes, "progressive").map(p => p.id)).toEqual(["a", "b"]);
  expect(filterPasses([{ ...base, progression_m: 100, progressive: false }], "progressive")).toEqual([]);
  expect(passSchema.safeParse({ ...base, progression_m: Infinity }).success).toBe(false);
});

for (const theme of ["Light", "Dark", "System"]) {
  it(`supports pass filtering, hover and keyboard alternatives in ${theme} theme`, async () => {
    const user = userEvent.setup();
    const { container } = render(<ThemeProvider><ThemeSwitcher/><PassingPitch passes={passes} player="P"/></ThemeProvider>);
    await user.click(screen.getByRole("button", { name: theme }));
    expect(screen.getByRole("button", { name: theme })).toHaveAttribute("aria-pressed", "true");
    expect(container.querySelectorAll("line[data-pass]")).toHaveLength(4);
    await user.hover(screen.getByRole("button", { name: /^Pass 1\./ }));
    expect(screen.getByText(/Progression 17.50 m equivalent/, { selector: "p" })).toBeInTheDocument();
    fireEvent.focus(screen.getByRole("button", { name: /^Pass 2\./ }));
    expect(screen.getByText(/Pass 2\. Period.*Progressive attempt, unsuccessful/, { selector: "p" })).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("button", { name: /^Pass 2\./ }), { key: "Escape" });
    expect(screen.getByText(/Hover, focus or select/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Pass filter"), "completed");
    expect(container.querySelectorAll("line[data-pass]")).toHaveLength(2);
    await user.selectOptions(screen.getByLabelText("Pass filter"), "unsuccessful");
    expect(container.querySelectorAll("line[data-pass]")).toHaveLength(2);
    expect(container.querySelectorAll("line[data-pass][stroke-dasharray]")).toHaveLength(2);
    await user.selectOptions(screen.getByLabelText("Pass filter"), "progressive");
    expect(container.querySelectorAll("line[data-pass]")).toHaveLength(2);
    await user.selectOptions(screen.getByLabelText("Pass filter"), "all");
    await user.click(screen.getByText(/Accessible pass details table/));
    const table = screen.getByRole("table", { name: /Filtered pass events/ });
    expect(within(table).getAllByRole("row")).toHaveLength(6);
    await user.click(screen.getByRole("button", { name: "Inspect pass 5" }));
    expect(screen.getByText(/Pass 5\. Period.*Unclassified \(invalid geometry\)/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear pass details" }));
    expect(screen.getByText(/Hover, focus or select/)).toBeInTheDocument();
  });
}

it("renders empty filters without hiding recorded-pass coverage", async () => {
  render(<PassingPitch passes={[{ ...base, progressive: false, completed_progressive: false }]} player="P"/>);
  await userEvent.selectOptions(screen.getByLabelText("Pass filter"), "progressive");
  expect(screen.getByText("No passes match this filter.")).toBeInTheDocument();
  expect(screen.getByText(/Showing 0 of 1 passes/)).toBeInTheDocument();
});

it("uses server definition for rankings and requests matching pass thresholds", async () => {
  const player: Player = { player_id: 100, player: "P", passes: 1, completed_passes: 1,
    pass_completion_pct: 100, shots: 0, goals: 0, xg: null, successful_dribbles: 0, successful_interceptions: 0 };
  const requested: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    requested.push(url);
    if (url.includes("/progressive-passing")) {
      const threshold = url.includes("threshold_m=20") ? 20 : 10;
      return new Response(JSON.stringify({ match_id: 1, team_id: 10,
        definition: { threshold_m: threshold, pitch_length_m: 105, pitch_width_m: 68, goal_x: 120, goal_y: 40, comparison: "greater_than_or_equal" },
        players: [{ rank: 1, player_id: 100, player: "P", passes: 1, valid_geometry: 1,
          progressive_attempts: threshold === 10 ? 1 : 0, completed_progressive: threshold === 10 ? 1 : 0,
          progressive_pct: threshold === 10 ? 100 : 0, net_progression_m: 17.5 }] }));
    }
    return new Response(JSON.stringify([{ ...base, progressive: !url.includes("threshold_m=20"), completed_progressive: !url.includes("threshold_m=20") }]));
  }));
  render(<SWRConfig value={{ provider: () => new Map() }}><ProgressivePassing matchId={1} teamId={10} players={[player]} player={player} onSelectPlayer={() => {}}/></SWRConfig>);
  await screen.findByRole("group", { name: /P passing map/ });
  const input = screen.getByLabelText("Minimum distance reduction (m equivalent)");
  await userEvent.clear(input);
  await userEvent.type(input, "20");
  await userEvent.click(screen.getByRole("button", { name: "Apply threshold" }));
  await screen.findByText(/at least 20 m-equivalent/);
  await screen.findByRole("group", { name: /P passing map/ });
  expect(requested.some(url => url.endsWith("progressive-passing?threshold_m=20"))).toBe(true);
  expect(requested.some(url => url.endsWith("passes?threshold_m=20"))).toBe(true);
  await userEvent.selectOptions(screen.getByLabelText("Pass filter"), "progressive");
  expect(screen.getByText("No passes match this filter.")).toBeInTheDocument();
});
