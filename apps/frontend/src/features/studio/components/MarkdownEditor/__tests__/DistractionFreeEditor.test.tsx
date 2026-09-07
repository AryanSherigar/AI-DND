import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DistractionFreeEditor } from "../DistractionFreeEditor";

describe("DistractionFreeEditor", () => {
  it("renders bold, italic, headings, and list items in preview", async () => {
    const user = userEvent.setup();
    render(
      <DistractionFreeEditor
        value={"# Title\n\n**bold** and *italic*\n\n- item one"}
        onChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /preview/i }));

    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
    expect(screen.getByText("bold").tagName).toBe("STRONG");
    expect(screen.getByText("italic").tagName).toBe("EM");
    expect(screen.getByText("item one").closest("li")).toBeInTheDocument();
  });

  it("renders an XSS payload as inert text instead of executing it", async () => {
    const user = userEvent.setup();
    const payload = '<img src="x" onerror="window.__xss = true">';
    render(<DistractionFreeEditor value={payload} onChange={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /preview/i }));

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect((window as unknown as { __xss?: boolean }).__xss).toBeUndefined();
  });

  it("renders a raw script tag as inert text instead of executing it", async () => {
    const user = userEvent.setup();
    const payload = "<script>window.__xss_script = true</script>";
    render(<DistractionFreeEditor value={payload} onChange={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /preview/i }));

    expect(document.querySelector("script")).not.toBeInTheDocument();
    expect(
      (window as unknown as { __xss_script?: boolean }).__xss_script,
    ).toBeUndefined();
  });
});
