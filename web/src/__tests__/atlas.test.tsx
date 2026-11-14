/** Smoke test of the demo path on mocked data: pick a site -> candidates
 * appear -> click one -> the report card renders with its groups. The
 * Playwright version of this against the real app is part of #15's follow-up. */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import App from "../App";
import type { MapPaneProps } from "../components/map/MapPane";

// jsdom has no canvas, so Leaflet itself can't run here. Stub the lazily
// loaded map with its props visible; the real map is checked in a browser.
vi.mock("../components/map/LeafletMap", () => ({
  default: ({ body, markers }: MapPaneProps) => (
    <div role="region" aria-label={`${body === "moon" ? "Moon" : "Earth"} map`}>
      {markers.length} markers
    </div>
  ),
}));

const renderApp = () =>
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );

describe("Atlas", () => {
  it("walks from a Moon base site to a report card", async () => {
    const user = userEvent.setup();
    renderApp();

    const select = await screen.findByLabelText("Target site");
    await user.selectOptions(select, "shackleton-rim");

    await waitFor(() => expect(screen.getByText(/12 candidates/)).toBeInTheDocument());
    expect(screen.getAllByText("new").length).toBeGreaterThan(0);

    // Two panes: the Moon site as the source, its Earth analogs on the other map.
    expect(await screen.findByRole("region", { name: "Moon map" })).toHaveTextContent("1 markers");
    expect(screen.getByRole("region", { name: "Earth map" })).toHaveTextContent("12 markers");

    // Earth is always the left pane, the Moon always the right one, whichever
    // body the search starts from.
    expect(screen.getAllByRole("region").map((r) => r.getAttribute("aria-label")))
      .toEqual(["Earth map", "Moon map"]);

    const first = screen.getByRole("button", { name: /77\.50°S/ });
    await user.click(first);

    await waitFor(() => expect(screen.getByText("Report card")).toBeInTheDocument());
    expect(screen.getByText("Where the analogy holds")).toBeInTheDocument();
    expect(screen.getByText("What Earth cannot reproduce")).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Atmosphere/ })).toBeInTheDocument();
  });

  it("shows the methodology page's honesty section", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole("link", { name: "Methodology" }));
    expect(await screen.findByText(/What the numbers are not/)).toBeInTheDocument();
  });
});
