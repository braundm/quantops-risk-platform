import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../src/App";

describe("App", () => {
  it("explains the product and its safety boundary", () => {
    render(<App />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Risk engineering you can trace.",
    );
    expect(screen.getByText(/does not execute trades/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open demo dashboard/i })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });
});
