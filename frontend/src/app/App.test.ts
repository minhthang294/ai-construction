import { describe, expect, it } from "vitest";
import { needsAcceptanceLeaveConfirmation, pickProjectId } from "./App";

describe("acceptance navigation guard", () => {
  it("warns when a dirty acceptance form leaves its page or project", () => {
    expect(needsAcceptanceLeaveConfirmation("acceptance", "dashboard", "a", "a", true)).toBe(true);
    expect(needsAcceptanceLeaveConfirmation("acceptance", "acceptance", "a", "b", true)).toBe(true);
  });

  it("allows staying put or leaving a clean form", () => {
    expect(needsAcceptanceLeaveConfirmation("acceptance", "acceptance", "a", "a", true)).toBe(false);
    expect(needsAcceptanceLeaveConfirmation("acceptance", "dashboard", "a", "a", false)).toBe(false);
  });
});

describe("recent project", () => {
  const projects = [{ id: "new", name: "New" }, { id: "old", name: "Old" }];
  it("opens the last available project after login", () => {
    expect(pickProjectId(projects, "", "old")).toBe("old");
    expect(pickProjectId(projects, "", "removed")).toBe("new");
    expect(pickProjectId(projects, "old", "new")).toBe("old");
  });
});
