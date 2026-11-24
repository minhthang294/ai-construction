import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import {
  COMPONENT_VIEWS,
  PAGE_SIZE,
  catalogEmptyMessage,
  catalogVerificationLabel,
  componentScopeLabel,
  componentTypeLabel,
  errorMessage,
  nextViewIndex,
  pageRemaining,
  segmentLabel,
} from "./componentCatalogImport";

function segment(overrides: Partial<Parameters<typeof segmentLabel>[0]> = {}) {
  return {
    id: "seg-1",
    number: 4,
    source_code: "S-4",
    zone: "Khu A",
    ...overrides,
  };
}

describe("componentCatalogImport labels", () => {
  it("returns the api, generic error, or unknown message", () => {
    expect(errorMessage(new ApiError("Hỏng máy chủ", 500))).toBe("Hỏng máy chủ");
    expect(errorMessage(new Error("Mất mạng"))).toBe("Mất mạng");
    expect(errorMessage("lạ")).toBe("Không xác định được lỗi.");
  });

  it("formats a segment as zone and number", () => {
    expect(segmentLabel(segment())).toBe("Khu A · PĐ 4");
  });

  it("labels pile and beam types", () => {
    expect(componentTypeLabel("pile")).toBe("Cọc");
    expect(componentTypeLabel("beam")).toBe("Dầm");
  });

  it("labels additional scope separately from design scope", () => {
    expect(componentScopeLabel("ADDITIONAL_SCOPE")).toBe("Phát sinh sửa chữa");
    expect(componentScopeLabel("DESIGN_SCOPE")).toBe("Theo thiết kế");
  });

  it("only marks VERIFIED rows as approved", () => {
    expect(catalogVerificationLabel("VERIFIED")).toBe("Đã duyệt danh mục");
    expect(catalogVerificationLabel("NEEDS_REVIEW")).toBe("Chờ duyệt");
  });

  it("picks the empty catalog message from the trimmed search", () => {
    expect(catalogEmptyMessage("")).toBe("Chưa có cấu kiện trong công trình.");
    expect(catalogEmptyMessage("   ")).toBe("Chưa có cấu kiện trong công trình.");
    expect(catalogEmptyMessage("I40-42")).toBe(
      "Không tìm thấy cấu kiện khớp mã hoặc alias.",
    );
  });
});

describe("componentCatalogImport tab keyboard navigation", () => {
  const last = COMPONENT_VIEWS.length - 1;

  it("maps Home and End to the first and last tab", () => {
    expect(nextViewIndex(2, "Home")).toBe(0);
    expect(nextViewIndex(2, "End")).toBe(last);
  });

  it("wraps arrow keys in both directions", () => {
    expect(nextViewIndex(0, "ArrowLeft")).toBe(last);
    expect(nextViewIndex(last, "ArrowRight")).toBe(0);
    expect(nextViewIndex(1, "ArrowRight")).toBe(2);
  });

  it("returns -1 for keys that do not move focus", () => {
    expect(nextViewIndex(1, "Enter")).toBe(-1);
    expect(nextViewIndex(1, "Tab")).toBe(-1);
  });
});

describe("componentCatalogImport pagination", () => {
  it("caps the next page at PAGE_SIZE and the remaining rows", () => {
    expect(pageRemaining(PAGE_SIZE + 5, PAGE_SIZE)).toBe(5);
    expect(pageRemaining(30, 20)).toBe(10);
    expect(pageRemaining(250, 100)).toBe(PAGE_SIZE);
  });
});
