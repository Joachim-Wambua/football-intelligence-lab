import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SWRConfig } from "swr";
import { describe, expect, it, vi } from "vitest";
import { MatchReport } from "@/components/match-report";
import { loadMatchReport, positiveReportId, reportHref } from "@/lib/match-report";
import { reportFixtures, reportSelection, reportTeam } from "./report-fixtures";
import { xtPlayersFixture } from "./xt-fixtures";

function mockApi(overrides: Record<string, unknown> = {}, failures: string[] = []) {
  const fixtures = { ...reportFixtures, ...overrides };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = url.split("/api/v1")[1];
    return new Response(JSON.stringify(fixtures[path] ?? {}), { status: failures.includes(path) ? 503 : path in fixtures ? 200 : 404 });
  }));
}
function report(selection = reportSelection) {
  const cache = new Map();
  const wrapper = ({ children }: { children: React.ReactNode }) => <SWRConfig value={{ provider: () => cache, dedupingInterval: 0 }}>{children}</SWRConfig>;
  return render(<MatchReport selection={selection}/>, { wrapper });
}
const exportButton = () => screen.getByRole("button", { name: "Print / Save as PDF" });
const readyReport = () => screen.findByRole("article", { name: "Match report: Team A vs Team B" });

describe("report evidence", () => {
  it("includes context, measured outcomes, partial xG coverage, Python leaders, definitions and provenance", async () => {
    mockApi();
    report();
    const content = within(await readyReport());
    expect(content.getByText(/2024-01-01.*Provider score: 1 : 0/)).toBeInTheDocument();
    expect(content.getByText(/Bundesliga.*2023\/24/)).toBeInTheDocument();
    expect(content.getByText("1 / 2 shots")).toBeInTheDocument();
    expect(content.getByRole("heading", { name: "Measured match outcomes" })).toBeInTheDocument();
    expect(content.getByRole("heading", { name: "Experimental xT · model estimates" })).toBeInTheDocument();
    expect(content.getByText(/6 training matches, 2 held out; 26 \/ 192 zones/)).toBeInTheDocument();
    expect(content.getByText(/Metric: shots.*excludes own-goal/)).toBeInTheDocument();
    expect(content.getByText(/17.5 m-equivalent/)).toBeInTheDocument();
    expect(content.getByRole("link", { name: "StatsBomb Open Data" })).toHaveAttribute("href", "https://github.com/statsbomb/open-data");
    expect(content.getByRole("table", { name: /progressive passing/ })).toHaveTextContent("Player A");
    expect(content.getByRole("table", { name: /Top five in API order/ })).toHaveTextContent("Unrated");
    expect(content.getByRole("table", { name: /All selected-team shots/ })).toHaveTextContent("Unknown player");
    expect(content.getByText(/1 events omitted/)).toBeInTheDocument();
    expect(exportButton()).toBeEnabled();
  });

  it("preserves no-shots semantics, missing scores, empty leaders", async () => {
    const matchPath = "/matches?competition_id=9&season_id=281";
    mockApi({
      [matchPath]: [{ match_id: 1, match_date: "2024-01-01", home_team: "Team A", away_team: "Team B", home_score: null, away_score: null }],
      "/matches/1/summary": { match_id: 1, event_count: 1, teams: [{ ...reportTeam, shots: 0, shot_goals: 0, recorded_xg: null, shots_with_xg: 0 }] },
      "/matches/1/shots?team_id=10": [],
      "/matches/1/teams/10/progressive-passing": { ...(reportFixtures["/matches/1/teams/10/progressive-passing"] as object), players: [] },
      "/matches/1/teams/10/xt/players": { ...xtPlayersFixture, players: [] },
    });
    report();
    await readyReport();
    expect(screen.getByText("No shot events recorded for this team.")).toBeInTheDocument();
    expect(screen.getByText("0 / 0 shots")).toBeInTheDocument();
    expect(screen.getByText(/Provider score: Unavailable : Unavailable/)).toBeInTheDocument();
    expect(screen.getByText("No named passers recorded.")).toBeInTheDocument();
    expect(screen.getByText("No identified move-makers recorded.")).toBeInTheDocument();
  });

  it("keeps a genuine zero xG visible in the report instead of unavailable", async () => {
    const shots = reportFixtures["/matches/1/shots?team_id=10"] as object[];
    mockApi({ "/matches/1/summary": { match_id: 1, event_count: 1, teams: [{ ...reportTeam, shots: 1, recorded_xg: 0, shots_with_xg: 1 }] }, "/matches/1/shots?team_id=10": [{ ...shots[0], xg: 0 }] });
    report();
    await readyReport();
    expect(screen.getByText("0.00")).toBeInTheDocument();
    expect(screen.getByText("0.000")).toBeInTheDocument();
    expect(screen.getByText("1 / 1 shots")).toBeInTheDocument();
  });

  it("labels optional failures and permits an explicitly incomplete printed report", async () => {
    mockApi({}, ["/xt/model", "/matches/1/shots?team_id=10"]);
    report();
    await readyReport();
    expect(screen.getByText(/Incomplete report/)).toBeInTheDocument();
    expect(screen.getAllByText(/Section unavailable:/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("heading", { name: "Measured match outcomes" })).toBeInTheDocument();
    expect(screen.queryByText("+0.3000")).not.toBeInTheDocument();
    expect(exportButton()).toBeEnabled();
  });

  it("withholds xT tables and insights from incompatible model versions", async () => {
    mockApi({ "/matches/1/teams/10/xt/players": { ...xtPlayersFixture, model_id: "different-artifact" } });
    report();
    await readyReport();
    expect(screen.getByText(/Model versions differ/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Experimental positive xT leader/ })).not.toBeInTheDocument();
    expect(screen.queryByText("+0.3000")).not.toBeInTheDocument();
  });

  it("blocks export for missing core context and supports retry", async () => {
    mockApi({}, ["/matches/1/summary"]);
    report();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(exportButton()).toBeDisabled();
    mockApi();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await readyReport();
    expect(exportButton()).toBeEnabled();
  });

  it("rejects valid-shaped evidence for a different team and a match outside its catalogue", async () => {
    mockApi({ "/matches/1/teams/10/progressive-passing": { ...(reportFixtures["/matches/1/teams/10/progressive-passing"] as object), team_id: 20 } });
    const data = await loadMatchReport(reportSelection);
    expect(data.progression.error).toMatch(/another match or team/);
    mockApi({ "/matches?competition_id=9&season_id=281": [] });
    await expect(loadMatchReport(reportSelection)).rejects.toThrow("not found in this report context");
  });
});

describe("report export and selection lifecycle", () => {
  it("requests browser printing only when evidence settles, without claiming a PDF was saved", async () => {
    mockApi();
    const fetchCurrent = globalThis.fetch;
    let finishModel!: (response: Response) => void;
    const pendingModel = new Promise<Response>(resolve => { finishModel = resolve; });
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => url.endsWith("/xt/model") ? pendingModel : fetchCurrent(url, init)));
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    const user = userEvent.setup();
    report();
    expect(exportButton()).toBeDisabled();
    await user.click(exportButton());
    expect(print).not.toHaveBeenCalled();
    await act(async () => { finishModel(new Response(JSON.stringify(reportFixtures["/xt/model"]))); });
    await readyReport();
    await user.click(exportButton());
    expect(print).toHaveBeenCalledOnce();
    expect(screen.getByText(/Print dialog requested/)).toBeInTheDocument();
    expect(screen.queryByText(/PDF saved successfully/)).not.toBeInTheDocument();
  });

  it("handles unavailable printing and copies a fully scoped live report link", async () => {
    mockApi();
    vi.spyOn(window, "print").mockImplementation(() => { throw new Error("unsupported"); });
    const user = userEvent.setup();
    const copy = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    report();
    await readyReport();
    await user.click(exportButton());
    expect(screen.getByText(/Printing is unavailable/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Copy report link" }));
    expect(copy).toHaveBeenCalledWith(new URL(reportHref(reportSelection), window.location.origin).href);
    expect(screen.getByText(/Report link copied/)).toBeInTheDocument();
    copy.mockRejectedValueOnce(new Error("permission denied"));
    await user.click(screen.getByRole("button", { name: "Copy report link" }));
    expect(screen.getByText(/Link could not be copied/)).toBeInTheDocument();
  });


  it("disables export and removes the snapshot during explicit refresh", async () => {
    mockApi();
    const view = report();
    await readyReport();
    const fetchCurrent = globalThis.fetch;
    let finishSummary!: (response: Response) => void;
    const pendingSummary = new Promise<Response>(resolve => { finishSummary = resolve; });
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => url.endsWith("/matches/1/summary") ? pendingSummary : fetchCurrent(url, init)));
    await userEvent.click(screen.getByRole("button", { name: "Refresh report" }));
    expect(exportButton()).toBeDisabled();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    await act(async () => { finishSummary(new Response(JSON.stringify(reportFixtures["/matches/1/summary"]))); });
    await readyReport();
    expect(exportButton()).toBeEnabled();
    view.unmount();
  });

  it("does not restore old report content when a previous match request finishes late", async () => {
    let finishOldShots!: (response: Response) => void;
    const oldShots = new Promise<Response>(resolve => { finishOldShots = resolve; });
    mockApi({ "/matches/2/summary": { match_id: 2, event_count: 2, teams: [{ ...reportTeam, team: "New A" }] } });
    const fetchCurrent = globalThis.fetch;
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => url.includes("/matches/1/shots?") ? oldShots : fetchCurrent(url, init)));
    const view = report();
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    view.rerender(<MatchReport selection={{ ...reportSelection, matchId: 2 }}/>);
    expect(exportButton()).toBeDisabled();
    expect(await screen.findByRole("article", { name: "Match report: New A vs New B" })).toBeInTheDocument();
    await act(async () => { finishOldShots(new Response(JSON.stringify(reportFixtures["/matches/1/shots?team_id=10"]))); });
    expect(screen.getByRole("article", { name: "Match report: New A vs New B" })).toBeInTheDocument();
    expect(screen.queryByRole("article", { name: "Match report: Team A vs Team B" })).not.toBeInTheDocument();
    expect(exportButton()).toBeEnabled();
  });

  it("removes a loaded report immediately when the selected team changes", async () => {
    mockApi();
    const view = report();
    await readyReport();
    view.rerender(<MatchReport selection={{ ...reportSelection, teamId: 20 }}/>);
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(exportButton()).toBeDisabled();
    expect(await screen.findByRole("article")).toHaveTextContent("Selected team: Team B");
    expect(screen.queryByRole("heading", { name: /Completed progressive-pass leader/ })).not.toBeInTheDocument();
  });
});

it("validates explicit positive safe IDs for shared URLs", () => {
  for (const invalid of [undefined, ["1", "2"], "0", "-1", "1.2", "1e3", "9007199254740992", "bad"]) expect(positiveReportId(invalid)).toBeNull();
  expect(positiveReportId("123")).toBe(123);
  expect(reportHref(reportSelection)).toBe("/reports/1?competition_id=9&season_id=281&team_id=10");
});
