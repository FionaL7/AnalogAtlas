/** The verdict block (#50/#52): the tier is ours; the provenance label always
 * says whether the paragraph involved an LLM. */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { wrapLabel } from "../components/MatchRadar";
import { ReportCard } from "../components/panels/ReportCard";
import { mockTwins } from "../lib/mocks";
import type { TwinsResponse } from "../lib/types";

const card = (data: TwinsResponse) => render(<MemoryRouter><ReportCard data={data} /></MemoryRouter>);

describe("verdict block", () => {
  it("shows the tier, the counts and the no-AI label without prose", () => {
    card(mockTwins("moonsp_2_3", "earth_-77.50_+162.00"));
    expect(screen.getByText("Moderate transfer confidence")).toBeInTheDocument();
    expect(screen.getByText("4 of 7 comparable dimensions hold")).toBeInTheDocument();
    expect(screen.getByText(/no AI involved/)).toBeInTheDocument();
  });

  it("shows the reviewed LLM prose and names the model when present", () => {
    const data = mockTwins("moonsp_2_3", "earth_-77.50_+162.00");
    data.verdict!.prose = { text: "A reviewed summary of the card.", model: "test-model-1" };
    card(data);
    expect(screen.getByText("A reviewed summary of the card.")).toBeInTheDocument();
    expect(screen.getByText(/drafted by test-model-1 .* reviewed by the team/)).toBeInTheDocument();
  });

  it("renders no verdict block on an old export without one", () => {
    const data = mockTwins("moonsp_2_3", "earth_-77.50_+162.00");
    delete data.verdict;
    card(data);
    expect(screen.queryByText(/transfer confidence/)).not.toBeInTheDocument();
  });
});

describe("match radar", () => {
  it("draws one spoke per compared dimension, each with its number", () => {
    const data = mockTwins("moonsp_2_3", "earth_-77.50_+162.00");
    card(data);
    const chart = screen.getByRole("img", { name: /Match by dimension/ });
    const compared = data.breakdown.filter((r) => r.kind === "compare" && r.match !== null);
    for (const r of compared) expect(chart.getAttribute("aria-label")).toContain(r.dimension);
  });

  it("wraps long labels onto two balanced lines", () => {
    expect(wrapLabel("Median slope")).toEqual(["Median slope"]);
    expect(wrapLabel("Surface temperature swing")).toEqual(["Surface", "temperature swing"]);
    expect(wrapLabel("Longest continuous darkness")).toEqual(["Longest continuous", "darkness"]);
  });
});
