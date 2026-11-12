import { describe, expect, it } from "vitest";
import {
  clampPageZoom,
  MAX_PAGE_ZOOM,
  MIN_PAGE_ZOOM,
  stepPageZoom,
} from "./pageViewport";

describe("page viewer zoom", () => {
  it("clamps zoom to the supported range", () => {
    expect(clampPageZoom(0)).toBe(MIN_PAGE_ZOOM);
    expect(clampPageZoom(Number.NaN)).toBe(MIN_PAGE_ZOOM);
    expect(clampPageZoom(Number.POSITIVE_INFINITY)).toBe(MIN_PAGE_ZOOM);
    expect(clampPageZoom(2.34)).toBe(2.34);
    expect(clampPageZoom(99)).toBe(MAX_PAGE_ZOOM);
  });

  it("steps by 25% and never leaves 100–400%", () => {
    expect(stepPageZoom(1, 1)).toBe(1.25);
    expect(stepPageZoom(1.25, -1)).toBe(1);
    expect(stepPageZoom(1, -1)).toBe(MIN_PAGE_ZOOM);
    expect(stepPageZoom(MAX_PAGE_ZOOM, 1)).toBe(MAX_PAGE_ZOOM);
  });
});
