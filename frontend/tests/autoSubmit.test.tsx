import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import AutoSubmitForm from "../components/AutoSubmitForm";
import { expectNoA11yViolations } from "./a11y";

const ui = (
  <AutoSubmitForm action="/league/1" submitLabel="Show team">
    <label>
      Team
      <select name="roster" defaultValue="1">
        <option value="1">Cole</option>
        <option value="2">Dad</option>
      </select>
    </label>
  </AutoSubmitForm>
);

describe("AutoSubmitForm", () => {
  it("is a GET form that submits itself when a choice changes", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    HTMLFormElement.prototype.requestSubmit = submit;
    render(ui);
    const form = screen.getByRole("combobox", { name: "Team" }).closest("form") as HTMLFormElement;
    expect(form).toHaveAttribute("method", "get");
    expect(form).toHaveAttribute("action", "/league/1");
    await user.selectOptions(screen.getByRole("combobox", { name: "Team" }), "2");
    expect(submit).toHaveBeenCalledTimes(1);
  });

  it("keeps a submit button only for browsers without JavaScript, and has no violations", async () => {
    render(ui);
    expect(screen.queryByRole("button", { name: "Show team" })).not.toBeInTheDocument();
    await expectNoA11yViolations(ui);
  });
});
