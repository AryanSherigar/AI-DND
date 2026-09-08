import { render, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Header } from "../Header";
import { useAuth } from "@/features/auth/hooks/useAuth";

vi.mock("@/features/auth/hooks/useAuth");

const mockUseAuth = vi.mocked(useAuth);

describe("Header", () => {
  const mockLogout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      loginWithGoogle: vi.fn(),
      loginAsDevUser: vi.fn(),
      logout: mockLogout,
    });
  });

  const renderAt = (path: string) =>
    render(
      <MemoryRouter initialEntries={[path]}>
        <Header />
      </MemoryRouter>,
    );

  it("shows the wordmark, nav links, and a sign-in link when logged out", () => {
    renderAt("/");

    expect(
      screen.getAllByRole("link", { name: "wevr" }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("link", { name: /discover/i }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("link", { name: /studio/i }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("link", { name: /sign in/i }).length,
    ).toBeGreaterThan(0);
  });

  it("opens the user menu and signs out when authenticated", () => {
    mockUseAuth.mockReturnValue({
      user: { user_id: "user-42", display_name: "Geralt of Rivia" },
      isAuthenticated: true,
      isLoading: false,
      error: null,
      loginWithGoogle: vi.fn(),
      loginAsDevUser: vi.fn(),
      logout: mockLogout,
    });

    renderAt("/");

    const trigger = screen.getByRole("button", { name: /geralt of rivia/i });
    expect(screen.queryByText("My creations")).not.toBeInTheDocument();

    fireEvent.click(trigger);
    const menu = screen.getByText("My creations").closest("div") as HTMLElement;
    expect(within(menu).getByText("Bookmarks")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it("toggles the mobile navigation menu", () => {
    renderAt("/");

    const toggle = screen.getByRole("button", {
      name: /toggle navigation menu/i,
    });
    fireEvent.click(toggle);

    // Menu now renders its own nav links in the mobile drawer.
    expect(
      screen.getAllByRole("link", { name: /discover/i }).length,
    ).toBeGreaterThan(1);
  });
});
