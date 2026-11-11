import { describe, expect, it } from "vitest";
import { addDaysISO, fromLocalInputValue, toLocalInputValue } from "./datetime";

describe("site report dates", () => {
  it("uses Asia/Ho_Chi_Minh for datetime-local, not the machine timezone", () => {
    expect(fromLocalInputValue("2026-11-11T09:30")).toBe(
      "2026-11-11T02:30:00.000Z",
    );
    expect(toLocalInputValue("2026-11-11T02:30:00Z")).toBe("2026-11-11T09:30");
    expect(fromLocalInputValue("")).toBeNull();
    expect(toLocalInputValue(null)).toBe("");
  });

  it("crosses month and year boundaries", () => {
    expect(addDaysISO("2026-11-11", 1)).toBe("2026-11-12");
    expect(addDaysISO("2026-11-30", 1)).toBe("2026-12-01");
    expect(addDaysISO("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDaysISO("2026-03-01", -1)).toBe("2026-02-28");
  });

  it("keeps the local calendar date for leap years", () => {
    expect(addDaysISO("2028-02-28", 1)).toBe("2028-02-29");
    expect(addDaysISO("2028-02-29", 1)).toBe("2028-03-01");
  });
});
