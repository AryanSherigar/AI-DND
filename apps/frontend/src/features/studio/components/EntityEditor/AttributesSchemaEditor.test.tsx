import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { AttributeFieldSchema } from "../../types/entity.types";
import { AttributesSchemaEditor } from "./AttributesSchemaEditor";

const Harness = (): React.ReactElement => {
  const [value, setValue] = useState<Record<string, AttributeFieldSchema>>({});
  return <AttributesSchemaEditor value={value} onChange={setValue} />;
};

describe("AttributesSchemaEditor", () => {
  it("adds an attribute row and shows min/max only for number type", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: /add attribute/i }));
    expect(screen.getByLabelText(/attribute key/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/attribute min/i)).not.toBeInTheDocument();

    await user.selectOptions(
      screen.getByLabelText(/attribute type/i),
      "number",
    );
    expect(screen.getByLabelText(/attribute min/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/attribute max/i)).toBeInTheDocument();

    await user.selectOptions(
      screen.getByLabelText(/attribute type/i),
      "string",
    );
    expect(screen.queryByLabelText(/attribute min/i)).not.toBeInTheDocument();
  });

  it("removes an attribute row", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: /add attribute/i }));
    expect(screen.getByLabelText(/attribute key/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /remove/i }));
    expect(screen.queryByLabelText(/attribute key/i)).not.toBeInTheDocument();
  });
});
