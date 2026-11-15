/** Hints (#53): visible text, and the "?" goes to the Methodology section. */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { Hint } from "../components/Hint";

describe("Hint", () => {
  it("shows its text without hovering", () => {
    render(<MemoryRouter><Hint>Hides sites already used as analogs.</Hint></MemoryRouter>);
    expect(screen.getByText("Hides sites already used as analogs.")).toBeVisible();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("links to the Methodology section it names", () => {
    render(<MemoryRouter><Hint more="glossary">Match: how close.</Hint></MemoryRouter>);
    expect(screen.getByRole("link", { name: "How this works" }))
      .toHaveAttribute("href", "/methodology#glossary");
  });
});
