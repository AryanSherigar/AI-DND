import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EBookActionDrawer } from "../EBook/EBookActionDrawer";

describe("EBookActionDrawer", () => {
  it("renders when open and submits action text", () => {
    const handleSubmit = vi.fn();
    const handleClose = vi.fn();

    render(
      <EBookActionDrawer
        isOpen={true}
        onClose={handleClose}
        onSubmit={handleSubmit}
        isNarrating={false}
      />,
    );

    const textarea = screen.getByPlaceholderText(/Action/i);
    fireEvent.change(textarea, {
      target: { value: "I inspect the ancient altar." },
    });

    const submitButton = screen.getByRole("button", { name: /Submit/i });
    fireEvent.click(submitButton);

    expect(handleSubmit).toHaveBeenCalledWith("I inspect the ancient altar.");
  });

  it("submits on Cmd+Enter shortcut", () => {
    const handleSubmit = vi.fn();
    const handleClose = vi.fn();

    render(
      <EBookActionDrawer
        isOpen={true}
        onClose={handleClose}
        onSubmit={handleSubmit}
        isNarrating={false}
      />,
    );

    const textarea = screen.getByPlaceholderText(/Action/i);
    fireEvent.change(textarea, { target: { value: "I light a torch." } });
    fireEvent.keyDown(textarea, { key: "Enter", metaKey: true });

    expect(handleSubmit).toHaveBeenCalledWith("I light a torch.");
  });

  it("calls onClose on Close button click or Escape key", () => {
    const handleClose = vi.fn();

    render(
      <EBookActionDrawer
        isOpen={true}
        onClose={handleClose}
        onSubmit={vi.fn()}
        isNarrating={false}
      />,
    );

    const closeButton = screen.getByRole("button", { name: /Close/i });
    fireEvent.click(closeButton);
    expect(handleClose).toHaveBeenCalledTimes(1);

    const textarea = screen.getByPlaceholderText(/Action/i);
    fireEvent.keyDown(textarea, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(2);
  });

  it("does not render when isOpen is false", () => {
    const { container } = render(
      <EBookActionDrawer
        isOpen={false}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        isNarrating={false}
      />,
    );

    expect(container.firstChild).toBeNull();
  });
});
