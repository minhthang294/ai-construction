import { describe, expect, it } from "vitest";
import {
  recordStatusLabel,
  requestStatusLabel,
  resultLabel,
  revisionLabel,
} from "./statusLabels";

describe("acceptance status labels", () => {
  it("maps request and record statuses to Vietnamese", () => {
    expect(requestStatusLabel("draft")).toBe("Nháp");
    expect(requestStatusLabel("submitted")).toBe("Đã gửi");
    expect(recordStatusLabel("draft")).toBe("Nháp");
    expect(recordStatusLabel("confirmed")).toBe("Đã xác nhận");
  });

  it("maps results and revision", () => {
    expect(resultLabel("approved")).toBe("Đồng ý");
    expect(resultLabel("conditional")).toBe("Đồng ý có điều kiện");
    expect(resultLabel("rejected")).toBe("Không đồng ý");
    expect(revisionLabel(2)).toBe("Bản sửa 2");
  });

  it("keeps unknown values visible", () => {
    expect(requestStatusLabel("other")).toBe("other");
  });
});
