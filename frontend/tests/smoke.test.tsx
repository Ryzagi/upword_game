import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "../src/App";
import "../src/i18n";

describe("App", () => {
  it("renders the main menu title", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/word describer/i);
  });

  it("renders the lobby title with the room code", () => {
    render(
      <MemoryRouter initialEntries={["/r/ABC123"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("ABC123");
  });
});
