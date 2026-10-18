import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SWRConfig } from "swr";
import { expect, it, vi } from "vitest";
import { ExpectedThreat } from "@/components/expected-threat";
import { XTHeatmap } from "@/components/xt-heatmap";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { filterXTActions, formatXT, xtModelSchema, xtActionSchema } from "@/lib/xt-contracts";
import { xtModelFixture as model, xtPlayersFixture, xtActionsFixture as actions } from "./xt-fixtures";

function mockAPI() {
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    requests.push(url);
    const data = url.endsWith("/xt/model") ? model : url.endsWith("/xt/players") ? xtPlayersFixture :
      { model_id: model.model_id, match_id: 1, team_id: 10, total: 4, offset: 0, limit: 200, actions };
    return new Response(JSON.stringify(data));
  }));
  return requests;
}
function renderPanel() {
  return render(<SWRConfig value={{ provider: () => new Map() }}><ExpectedThreat matchId={1} teamId={10}/></SWRConfig>);
}

it("preserves zero/null/signed values and filters only server-valued actions", () => {
  expect(filterXTActions(actions, "Pass", "all")).toHaveLength(3);
  expect(filterXTActions(actions, "Carry", "negative").map(a => a.id)).toEqual(["b"]);
  expect(filterXTActions(actions, "all", "positive").map(a => a.id)).toEqual(["a"]);
  expect(formatXT(0)).toBe("0.0000");
  expect(formatXT(null)).toBe("Unrated");
  expect(formatXT(-.1)).toBe("-0.1000");
  expect(xtActionSchema.safeParse({ ...actions[0], xt: Infinity }).success).toBe(false);
  expect(xtModelSchema.safeParse({ ...model, surface: [[.1]] }).success).toBe(false);
});

for (const theme of ["Light", "Dark", "System"]) {
  it(`renders actual 192-zone grid with keyboard/hover alternatives in ${theme}`, async () => {
    const user = userEvent.setup();
    const { container } = render(<ThemeProvider><ThemeSwitcher/><XTHeatmap model={model} actions={actions}/></ThemeProvider>);
    await user.click(screen.getByRole("button", { name: theme }));
    expect(screen.getByRole("button", { name: theme })).toHaveAttribute("aria-pressed", "true");
    expect(container.querySelectorAll("rect[data-zone]")).toHaveLength(192);
    expect(container.querySelectorAll("line[data-xt-action]")).toHaveLength(3); // zero draws, null doesn't
    const zone = screen.getByRole("button", { name: /^Zone row 1, column 1:/ });
    await user.hover(zone);
    const label = zone.getAttribute("aria-label")!;
    expect(screen.getByText(label, { selector: "p" })).toBeInTheDocument();
    fireEvent.focus(zone);
    fireEvent.keyDown(zone, { key: "Enter" });
    expect(zone).toHaveAttribute("aria-pressed", "true");
    fireEvent.keyDown(zone, { key: "Escape" });
    expect(screen.getByText("Hover or focus a zone to inspect its value.")).toBeInTheDocument();
    await user.click(screen.getByText("Zone values and observed shot support"));
    expect(within(screen.getByRole("table", { name: /All fitted xT zones/ })).getAllByRole("row")).toHaveLength(193);
    expect(label).toContain(model.surface[0][0].toFixed(6));
  });
}

it("loads rankings, displays limitations and optionally overlays a filtered bounded page", async () => {
  const requests = mockAPI();
  const user = userEvent.setup();
  const { container } = renderPanel();
  expect(await screen.findByRole("table", { name: "Model-based player xT totals" })).toHaveTextContent("+0.3000");
  expect(screen.getByText(/Experimental xT — six Leverkusen/)).toHaveTextContent("26 of 192");
  expect(screen.getAllByText("Unrated")).toHaveLength(2);
  expect(requests.some(url => url.includes("/xt/actions"))).toBe(false);
  await user.click(screen.getByRole("checkbox"));
  await screen.findByText(/Page offset 0/);
  expect(container.querySelectorAll("line[data-xt-action]")).toHaveLength(3);
  await user.selectOptions(screen.getByLabelText("xT action type"), "Carry");
  await user.selectOptions(screen.getByLabelText("xT change"), "negative");
  expect(container.querySelectorAll("line[data-xt-action]")).toHaveLength(1);
  expect(container.querySelector("line[data-xt-action]")).toHaveAttribute("stroke-dasharray");
  await user.selectOptions(screen.getByLabelText("xT action type"), "all");
  await user.selectOptions(screen.getByLabelText("xT change"), "all");
  await user.click(screen.getByText(/Valued action details/));
  const table = screen.getByRole("table", { name: /xT action page including/ });
  expect(table).toHaveTextContent("-0.1000");
  expect(table).toHaveTextContent("0.0000");
  expect(table).toHaveTextContent("Unrated");
  expect(screen.getByRole("button", { name: "Next actions" })).toBeDisabled();
});

it("keeps an explicit experimental notice when the model is unavailable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 503 })));
  renderPanel();
  expect(await screen.findByRole("alert")).toHaveTextContent("experimental xT model is unavailable");
  expect(screen.getByText(/Experimental xT — six Leverkusen/)).toBeInTheDocument();
});
