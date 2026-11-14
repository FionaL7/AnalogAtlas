/** Smoke test of the demo path on mocked data: pick a site -> candidates
 * appear -> click one -> the report card renders with its groups. The
 * Playwright version of this against the real app is part of #15's follow-up. */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import App from "../App";
import type { MapPaneProps } from "../components/map/MapPane";

// jsdom has no canvas, so Leaflet itself can't run here. Stub the lazily
// loaded map with its props visible; the real map is checked in a browser.
// Labels must match LeafletMap's BODY_LABEL, or the pane assertions below
// stop meaning anything.
const BODY_LABEL: Record<string, string> = {
  moon: "Moon",
  moon_polar: "Moon south pole",
  earth: "Earth",
};

// A click inside each body's index, so the stub can exercise map-click search.
const CLICK_AT: Record<string, [number, number]> = {
  moon: [10, 20], moon_polar: [-86, 0], earth: [-24.1, -69.9],
};

vi.mock("../components/map/LeafletMap", () => ({
  default: ({ body, markers, onMapClick }: MapPaneProps) => (
    <div role="region" aria-label={`${BODY_LABEL[body]} map`}>
      {markers.length} markers
      {onMapClick && (
        <button type="button" onClick={() => onMapClick(...CLICK_AT[body])}>
          click {body} map
        </button>
      )}
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

    // Two panes: the Moon site as the source, its Earth analogs on the other
    // map. Shackleton is an Artemis base region at 89.7°S, so it belongs to
    // `moon_polar` and must open the polar pane, not the lat/lon Moon one (#26).
    expect(await screen.findByRole("region", { name: "Moon south pole map" }))
      .toHaveTextContent("1 markers");
    expect(screen.getByRole("region", { name: "Earth map" })).toHaveTextContent("12 markers");

    // Earth is always the left pane, the lunar body always the right one,
    // whichever body the search starts from.
    expect(screen.getAllByRole("region").map((r) => r.getAttribute("aria-label")))
      .toEqual(["Earth map", "Moon south pole map"]);

    const first = screen.getByRole("button", { name: /77\.50°S/ });
    await user.click(first);

    await waitFor(() => expect(screen.getByText("Report card")).toBeInTheDocument());
    expect(screen.getByText("Where the analogy holds")).toBeInTheDocument();
    expect(screen.getByText("What Earth cannot reproduce")).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Atmosphere/ })).toBeInTheDocument();

    // Both tiles as pictures, and what to test there (C6).
    expect(screen.getByText(/Side by side/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Earth tile near/ })).toBeInTheDocument();
    expect(screen.getByText("What to test here")).toBeInTheDocument();
    expect(screen.getByText("Rover mobility and traverse planning")).toBeInTheDocument();
    expect(screen.getByText(/Analog model:/)).toBeInTheDocument();
  });

  it("shows text search results, and a picked result becomes the source", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.type(await screen.findByLabelText("Describe a landscape"), "smooth plains");
    await user.click(screen.getByRole("button", { name: "Search" }));

    const results = await screen.findByRole("region", { name: "Search results" });
    expect(results).toHaveTextContent(/12 matches on the Moon/);
    expect(screen.getByRole("region", { name: "Moon map" })).toHaveTextContent("12 markers");

    await user.click(within(results).getAllByRole("button", { name: /°/ })[0]);
    await waitFor(() => expect(screen.getByText(/12 candidates on Earth/)).toBeInTheDocument());
    expect(screen.queryByRole("region", { name: "Search results" })).not.toBeInTheDocument();
  });

  it("starts an analog search from a map click", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(await screen.findByRole("button", { name: "click earth map" }));
    // From Earth, the analogs are Moon tiles.
    await waitFor(() => expect(screen.getByText(/candidates on Moon/)).toBeInTheDocument());
    expect(screen.getByText(/Searching from Earth/)).toBeInTheDocument();
  });

  it("shows the methodology page's honesty section", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole("link", { name: "Methodology" }));
    expect(await screen.findByText(/What the numbers are not/)).toBeInTheDocument();
  });
});
