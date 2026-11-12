import { describe, expect, it } from "vitest";
import { nextTabIndex } from "./tabNavigation";

describe("engineering AI tab navigation", () => {
  it("wraps with left and right arrow keys", () => {
    expect(nextTabIndex(0, "ArrowRight", 6)).toBe(1);
    expect(nextTabIndex(5, "ArrowRight", 6)).toBe(0);
    expect(nextTabIndex(0, "ArrowLeft", 6)).toBe(5);
    expect(nextTabIndex(3, "ArrowLeft", 6)).toBe(2);
  });

  it("moves to the first and last tab with Home and End", () => {
    expect(nextTabIndex(3, "Home", 6)).toBe(0);
    expect(nextTabIndex(3, "End", 6)).toBe(5);
  });

  it("ignores unrelated keys and empty tab lists", () => {
    expect(nextTabIndex(2, "Enter", 6)).toBeNull();
    expect(nextTabIndex(2, "ArrowRight", 0)).toBeNull();
  });

  it("clamps an out-of-range current index", () => {
    expect(nextTabIndex(99, "ArrowRight", 6)).toBe(0);
    expect(nextTabIndex(-4, "ArrowLeft", 6)).toBe(5);
  });
});
