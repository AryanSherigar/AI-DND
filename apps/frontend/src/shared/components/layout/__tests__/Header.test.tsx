import { render, screen, fireEvent } from "@testing-library/react";
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

  it("renders brand logo, platform links, and Sign In when logged out", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Header variant="landing" />
      </MemoryRouter>,
    );

    expect(screen.getByText("AI-DND")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /discover/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /studio/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /sign in/i })).toBeInTheDocument();
  });

  it("renders user badge and opens dropdown menu when authenticated", () => {
    mockUseAuth.mockReturnValue({
      user: { user_id: "user-42", display_name: "Geralt of Rivia" },
      isAuthenticated: true,
      isLoading: false,
      error: null,
      loginWithGoogle: vi.fn(),
      loginAsDevUser: vi.fn(),
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Header />
      </MemoryRouter>,
    );

    const userBadge = screen.getByText("Geralt of Rivia");
    expect(userBadge).toBeInTheDocument();

    // Dropdown is initially not visible
    expect(screen.queryByText("Adventurer Profile")).not.toBeInTheDocument();

    // Open dropdown
    fireEvent.click(userBadge);

    expect(screen.getByText("Adventurer Profile")).toBeInTheDocument();
    expect(screen.getByText("My Creations")).toBeInTheDocument();
    expect(screen.getByText("Bookmarks")).toBeInTheDocument();

    // Click Sign Out
    const signOutBtn = screen.getByRole("button", { name: /sign out/i });
    fireEvent.click(signOutBtn);
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it("highlights active link on /discover", () => {
    render(
      <MemoryRouter initialEntries={["/discover"]}>
        <Header />
      </MemoryRouter>,
    );

    const discoverLink = screen.getByRole("link", { name: /discover/i });
    expect(discoverLink).toHaveClass("text-amber-300");
  });

  it("toggles mobile navigation drawer on hamburger click", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Header />
      </MemoryRouter>,
    );

    const toggleButton = screen.getByRole("button", {
      name: /toggle navigation menu/i,
    });
    expect(toggleButton).toBeInTheDocument();

    // Open mobile menu
    fireEvent.click(toggleButton);
    expect(screen.getByText("✕")).toBeInTheDocument();

    // Close mobile menu
    fireEvent.click(toggleButton);
    expect(screen.getByText("☰")).toBeInTheDocument();
  });

  it("smooth scrolls to top when logo is clicked on landing route", () => {
    const scrollToMock = vi.fn();
    window.scrollTo = scrollToMock;

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Header variant="landing" />
      </MemoryRouter>,
    );

    const logoLink = screen.getByTitle("Return to Realm Gateway");
    fireEvent.click(logoLink);

    expect(scrollToMock).toHaveBeenCalledWith({
      top: 0,
      behavior: "smooth",
    });
  });

  it("transitions scroll styles for landing variant", () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/"]}>
        <Header variant="landing" />
      </MemoryRouter>,
    );

    const headerElement = container.querySelector("header");
    expect(headerElement).toHaveClass("bg-transparent");

    // Simulate scroll past threshold
    Object.defineProperty(window, "scrollY", { value: 100, writable: true });
    fireEvent.scroll(window);

    expect(headerElement).toHaveClass("bg-[#0d0f14]/90");
  });
});
