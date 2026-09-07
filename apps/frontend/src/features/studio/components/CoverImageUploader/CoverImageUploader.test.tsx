import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "@/test/msw/server";
import { CoverImageUploader } from "./CoverImageUploader";

const API_URL = "http://localhost:8000";

const renderComponent = (
  props: React.ComponentProps<typeof CoverImageUploader>,
): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <CoverImageUploader {...props} />
    </QueryClientProvider>,
  );
};

describe("CoverImageUploader", () => {
  it("renders empty state with label and upload prompt", () => {
    renderComponent({
      label: "Cover Image",
      value: null,
      onChange: vi.fn(),
    });

    expect(screen.getByText("Cover Image")).toBeInTheDocument();
    expect(
      screen.getByText("Click to upload or drag an image here"),
    ).toBeInTheDocument();
  });

  it("renders image preview and removes image when remove button is clicked", async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();

    renderComponent({
      label: "Cover Image",
      value: "http://localhost:8000/uploads/scenario-covers/test.png",
      onChange: handleChange,
    });

    const preview = screen.getByAltText("Scenario cover preview");
    expect(preview).toBeInTheDocument();
    expect(preview).toHaveAttribute(
      "src",
      "http://localhost:8000/uploads/scenario-covers/test.png",
    );

    const removeBtn = screen.getByRole("button", { name: /remove image/i });
    await user.click(removeBtn);

    expect(handleChange).toHaveBeenCalledWith(null);
  });

  it("uploads an image successfully and triggers onChange", async () => {
    const handleChange = vi.fn();
    const uploadedUrl =
      "http://localhost:8000/uploads/scenario-covers/new-image.png";

    server.use(
      http.post(`${API_URL}/v1/uploads/scenario-cover-image`, () =>
        HttpResponse.json({ url: uploadedUrl }),
      ),
    );

    const user = userEvent.setup();
    renderComponent({
      label: "Cover Image",
      value: null,
      onChange: handleChange,
    });

    const file = new File(["dummy content"], "cover.png", {
      type: "image/png",
    });
    const input = screen.getByLabelText("Cover Image");

    await user.upload(input, file);

    await waitFor(() => {
      expect(handleChange).toHaveBeenCalledWith(uploadedUrl);
    });
  });

  it("shows error for unsupported image format", async () => {
    const handleChange = vi.fn();

    renderComponent({
      label: "Cover Image",
      value: null,
      onChange: handleChange,
    });

    const file = new File(["pdf content"], "document.pdf", {
      type: "application/pdf",
    });
    const input = screen.getByLabelText("Cover Image");

    fireEvent.change(input, { target: { files: [file] } });

    expect(
      await screen.findByText(/unsupported image format/i),
    ).toBeInTheDocument();
    expect(handleChange).not.toHaveBeenCalled();
  });

  it("shows error for oversized file", async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();

    renderComponent({
      label: "Cover Image",
      value: null,
      onChange: handleChange,
    });

    // Create file larger than 5MB
    const largeBlob = new Blob([new Uint8Array(5 * 1024 * 1024 + 10)], {
      type: "image/png",
    });
    const file = new File([largeBlob], "huge.png", { type: "image/png" });
    const input = screen.getByLabelText("Cover Image");

    await user.upload(input, file);

    expect(
      await screen.findByText(/exceeds the 5mb size limit/i),
    ).toBeInTheDocument();
    expect(handleChange).not.toHaveBeenCalled();
  });
});
