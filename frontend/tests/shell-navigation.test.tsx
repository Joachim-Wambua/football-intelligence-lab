import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { usePathname } from "next/navigation";
import { Shell } from "@/components/shell";
vi.mock("next/navigation", () => ({ usePathname: vi.fn() }));

it("preserves the match URL query when following a workspace section link", async () => {
  vi.mocked(usePathname).mockReturnValue("/");
  const original = window.location.href;
  window.history.replaceState({}, "", "/?competition_id=43&season_id=3&match_id=4&team_id=40");
  try {
    render(<Shell><p>Match workspace</p></Shell>);
    await userEvent.click(screen.getByRole("button", { name: "Menu" }));
    const link = screen.getByRole("link", { name: /Passing intelligence/ });
    expect(link).toHaveAttribute("href", "#passes");
    await userEvent.click(link);
    await waitFor(() => expect(window.location.hash).toBe("#passes"));
    expect(window.location.search).toBe("?competition_id=43&season_id=3&match_id=4&team_id=40");
  } finally { window.history.replaceState({}, "", original); }
});

it("links to Match Intelligence from the separate player module", () => {
  vi.mocked(usePathname).mockReturnValue("/players");
  render(<Shell><p>Player workspace</p></Shell>);
  expect(screen.getByRole("link", { name: /Passing intelligence/ })).toHaveAttribute("href", "/#passes");
});
