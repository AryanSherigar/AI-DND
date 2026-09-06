import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { usePlayStore } from "../../../../stores/play.store";
import { ReaderTypographyMenu } from "../ReaderTypographyMenu";

describe("ReaderTypographyMenu", () => {
  beforeEach(() => {
    usePlayStore.setState({
      reader_font_override: null,
      playthrough: null,
    });
  });

  it("renders the typography Aa button", () => {
    render(<ReaderTypographyMenu />);
    expect(
      screen.getByRole("button", { name: /typography settings/i }),
    ).toBeInTheDocument();
  });

  it("opens the typography menu and allows selecting an override font", async () => {
    const user = userEvent.setup();
    render(<ReaderTypographyMenu />);

    const button = screen.getByRole("button", { name: /typography settings/i });
    await user.click(button);

    const select = screen.getByLabelText(/reader narration font/i);
    expect(select).toBeInTheDocument();

    await user.selectOptions(select, "special-elite");
    expect(usePlayStore.getState().reader_font_override).toBe("special-elite");

    await user.selectOptions(select, "default");
    expect(usePlayStore.getState().reader_font_override).toBeNull();
  });
});
