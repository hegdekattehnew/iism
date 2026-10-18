// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiError, apiErrorFrom } from "@/lib/http";
import { renderUi } from "@/test/harness";

import { Checkbox, Field, FormErrors, Input, Select, Textarea } from "./field";
import { problemWith } from "./validate";

const box = (name: string) => screen.getByLabelText(name) as HTMLInputElement;

describe("Field wires its control", () => {
  it("ties the label to the control by id, so the control's name is the label and nothing else", () => {
    renderUi(
      <Field label="Course title" hint="At least three characters.">
        <Input />
      </Field>,
    );
    expect(screen.getByRole("textbox", { name: "Course title" })).toBeTruthy();
  });

  it("names the hint as the control's description", () => {
    renderUi(
      <Field label="Title" hint="At least three characters.">
        <Input />
      </Field>,
    );
    const input = box("Title");
    const hint = screen.getByText("At least three characters.");
    expect(input.getAttribute("aria-describedby")).toBe(hint.id);
    expect(input.getAttribute("aria-invalid")).toBeNull();
  });

  it("works for a textarea and a select as it does for an input", () => {
    renderUi(
      <>
        <Field label="About">
          <Textarea />
        </Field>
        <Field label="Level">
          <Select>
            <option value="a">A</option>
          </Select>
        </Field>
      </>,
    );
    expect(screen.getByRole("textbox", { name: "About" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Level" })).toBeTruthy();
  });

  it("every control is at least 44 px tall, and so is a checkbox's label", () => {
    renderUi(
      <>
        <Field label="A">
          <Input />
        </Field>
        <Field label="B">
          <Textarea />
        </Field>
        <Field label="C">
          <Select />
        </Field>
        <Checkbox label="D" />
      </>,
    );
    for (const name of ["A", "B", "C"]) expect(box(name).className).toContain("min-h-11");
    expect(screen.getByText("D").closest("label")!.className).toContain("min-h-11");
  });

  it("a control outside a Field still renders, with no wiring to make", () => {
    render(<Input aria-label="Loose" />);
    expect(screen.getByLabelText("Loose")).toBeTruthy();
  });
});

describe("a problem next to its field when the person leaves it", () => {
  it("says the value is too short, in the page's words with the number, once the field is left", async () => {
    renderUi(
      <Field label="Title">
        <Input minLength={3} />
      </Field>,
    );
    const input = box("Title");
    fireEvent.change(input, { target: { value: "ab" } });
    // The check is a chunk loaded on first use: give it every chance to answer before saying it did not.
    await new Promise((done) => setTimeout(done, 30));
    expect(screen.queryByRole("alert")).toBeNull(); // not nagged while typing
    fireEvent.blur(input);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("Use at least 3 characters.");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(input.getAttribute("aria-describedby")).toContain(alert.id);
  });

  it("goes away as soon as the value is fixed", async () => {
    renderUi(
      <Field label="Title">
        <Input minLength={3} />
      </Field>,
    );
    const input = box("Title");
    fireEvent.change(input, { target: { value: "ab" } });
    fireEvent.blur(input);
    expect(await screen.findByRole("alert")).toBeTruthy();
    fireEvent.change(input, { target: { value: "abc" } });
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(input.getAttribute("aria-invalid")).toBeNull();
  });

  it("an empty optional field is not a problem, an empty required one is", async () => {
    renderUi(
      <>
        <Field label="Optional">
          <Input minLength={3} />
        </Field>
        <Field label="Needed">
          <Input required />
        </Field>
      </>,
    );
    fireEvent.blur(box("Optional"));
    fireEvent.blur(box("Needed"));
    expect((await screen.findByRole("alert")).textContent).toBe("Fill in this field.");
    expect(screen.getAllByRole("alert")).toHaveLength(1); // only the required one complained
  });

  it("names the range a number is outside", async () => {
    renderUi(
      <Field label="Seats">
        <Input type="number" min={1} max={999} />
      </Field>,
    );
    const input = box("Seats");
    fireEvent.change(input, { target: { value: "0" } });
    fireEvent.blur(input);
    expect((await screen.findByRole("alert")).textContent).toBe("Enter 1 or more.");
    fireEvent.change(input, { target: { value: "1000" } });
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("Enter 999 or less."));
  });

  it("says what kind of address an email or a web field wants", async () => {
    renderUi(
      <>
        <Field label="Mail">
          <Input type="email" />
        </Field>
        <Field label="Site">
          <Input type="url" />
        </Field>
      </>,
    );
    fireEvent.change(box("Mail"), { target: { value: "not-an-address" } });
    fireEvent.blur(box("Mail"));
    fireEvent.change(box("Site"), { target: { value: "not a url" } });
    fireEvent.blur(box("Site"));
    await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(2));
    const messages = screen.getAllByRole("alert").map((a) => a.textContent);
    expect(messages).toEqual(["Enter an email address, like name@example.com.", "Enter a web address that starts with https://"]);
  });

  it("still calls the handlers the form gave the control", () => {
    let blurred = 0;
    let changed = "";
    renderUi(
      <Field label="Title">
        <Input onBlur={() => blurred++} onChange={(e) => (changed = e.target.value)} />
      </Field>,
    );
    fireEvent.change(box("Title"), { target: { value: "x" } });
    fireEvent.blur(box("Title"));
    expect([blurred, changed]).toEqual([1, "x"]);
  });
});

describe("what the server said about a field", () => {
  const refused = apiErrorFrom(422, {
    detail: [{ loc: ["body", "title"], msg: "String should have at least 3 characters" }],
  });

  it("is shown next to that field, in the server's own words, and not next to another", () => {
    renderUi(
      <FormErrors fields={refused.fields}>
        <Field label="Title" name="title">
          <Input />
        </Field>
        <Field label="Description" name="description">
          <Textarea />
        </Field>
      </FormErrors>,
    );
    expect(screen.getByRole("alert").textContent).toBe("String should have at least 3 characters");
    expect(box("Title").getAttribute("aria-invalid")).toBe("true");
    expect(box("Description").getAttribute("aria-invalid")).toBeNull();
  });

  it("finds its field by the control's own name, the way every form here names them", () => {
    renderUi(
      <FormErrors fields={refused.fields}>
        <Field label="Title">
          <Input name="title" />
        </Field>
        <Field label="Description">
          <Textarea name="description" />
        </Field>
      </FormErrors>,
    );
    expect(screen.getAllByRole("alert").map((a) => a.textContent)).toEqual(["String should have at least 3 characters"]);
    expect(box("Title").getAttribute("aria-invalid")).toBe("true");
  });

  it("goes away when the person edits that field", () => {
    renderUi(
      <FormErrors fields={refused.fields}>
        <Field label="Title" name="title">
          <Input />
        </Field>
      </FormErrors>,
    );
    fireEvent.change(box("Title"), { target: { value: "A longer title" } });
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("an error the form passes directly wins over the server's and the browser's", () => {
    renderUi(
      <FormErrors fields={refused.fields}>
        <Field label="Title" name="title" error="Choose another title.">
          <Input />
        </Field>
      </FormErrors>,
    );
    expect(screen.getByRole("alert").textContent).toBe("Choose another title.");
  });

  it("a failure that names no field adds nothing here", () => {
    renderUi(
      <FormErrors fields={new ApiError(500, null).fields}>
        <Field label="Title" name="title">
          <Input />
        </Field>
      </FormErrors>,
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("problemWith", () => {
  const make = (attrs: Record<string, string>, value: string) => {
    const el = document.createElement("input");
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    el.value = value;
    return el;
  };

  it("finds a too-short value that a script put there (the browser only checks what was typed)", () => {
    expect(problemWith(make({ minlength: "3" }, "ab"))).toEqual({ key: "tooShort", values: { min: 3 } });
  });

  it("finds a too-long one", () => {
    expect(problemWith(make({ maxlength: "2" }, "abc"))).toEqual({ key: "tooLong", values: { max: 2 } });
  });

  it("finds nothing wrong with a value inside its limits", () => {
    expect(problemWith(make({ minlength: "3", maxlength: "5" }, "abcd"))).toBeNull();
    expect(problemWith(make({}, ""))).toBeNull();
  });
});
