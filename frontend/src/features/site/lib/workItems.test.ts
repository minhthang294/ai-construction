import { describe, expect, it } from "vitest";
import {
  buildWorkItemGroups,
  formatWorkLogLabel,
  groupWorkItemNames,
  uniqueWorkItemNames,
  workItemGroupForName,
  workItemNameById,
} from "./workItems";

const CATALOG_NAMES = [
  "Đục bỏ bê tông om vỡ",
  "Tẩy gỉ bề mặt",
  "Vệ sinh quét keo epoxy",
  "Lắp đặt tấm vỏ",
  "Khoan cấy thép",
  "Đục bỏ bê tông om vỡ các cọc phát sinh",
  "Đục bỏ bê tông om vỡ dầm phát sinh",
];

/** The real catalog has 41 rows but repeats these seven names. */
function catalogRows() {
  return Array.from({ length: 41 }, (_, index) => ({
    id: `w${index + 1}`,
    name: CATALOG_NAMES[index % CATALOG_NAMES.length],
  }));
}

describe("unique work item options", () => {
  it("collapses 41 catalog rows into seven unique names", () => {
    const names = uniqueWorkItemNames(catalogRows());
    expect(names).toHaveLength(7);
    expect(names).toEqual(CATALOG_NAMES);
  });

  it("groups the seven names into the six business groups", () => {
    const groups = buildWorkItemGroups(catalogRows());
    expect(groups.map((group) => group.label)).toEqual([
      "Đục phá",
      "Xử lý bề mặt",
      "Vệ sinh/kết dính",
      "Khoan cấy",
      "Lắp đặt/bơm vữa",
    ]);
    expect(groups.find((group) => group.key === "duc_pha")?.names).toEqual([
      "Đục bỏ bê tông om vỡ",
      "Đục bỏ bê tông om vỡ các cọc phát sinh",
      "Đục bỏ bê tông om vỡ dầm phát sinh",
    ]);
    expect(
      groups.reduce((total, group) => total + group.names.length, 0),
    ).toBe(7);
  });

  it("classifies names by keyword without an id lookup", () => {
    expect(workItemGroupForName("Đục bỏ bê tông om vỡ")).toBe("duc_pha");
    expect(workItemGroupForName("Tẩy gỉ bề mặt")).toBe("xu_ly_be_mat");
    expect(workItemGroupForName("Vệ sinh quét keo epoxy")).toBe(
      "ve_sinh_ket_dinh",
    );
    expect(workItemGroupForName("Khoan cấy thép")).toBe("khoan_cay");
    expect(workItemGroupForName("Lắp đặt tấm vỏ")).toBe("lap_dat_bom_vua");
    expect(workItemGroupForName("Công tác khác")).toBe("khac");
  });

  it("keeps a report-only name that is no longer in the catalog", () => {
    const groups = groupWorkItemNames([
      ...CATALOG_NAMES,
      "Công tác ngoài danh mục",
    ]);
    const other = groups.find((group) => group.key === "khac");
    expect(other?.names).toEqual(["Công tác ngoài danh mục"]);
    expect(buildWorkItemGroups([], ["Công tác ngoài danh mục"])).toEqual([
      {
        key: "khac",
        label: "Khác",
        names: ["Công tác ngoài danh mục"],
      },
    ]);
  });

  it("maps ids to names for legacy work_item_id reports", () => {
    const byId = workItemNameById([
      { id: "w1", name: " Đục bỏ bê tông om vỡ " },
      { id: "w2", name: "Khoan cấy thép" },
    ]);
    expect(byId.get("w1")).toBe("Đục bỏ bê tông om vỡ");
    expect(byId.get("missing")).toBeUndefined();
  });
});

describe("work log export label", () => {
  it("renders 'name tại location'", () => {
    expect(
      formatWorkLogLabel({ name: "Đục bỏ bê tông om vỡ", location: "Cọc A2, A8" }),
    ).toBe("Đục bỏ bê tông om vỡ tại Cọc A2, A8");
  });

  it("falls back to component when location is empty", () => {
    expect(
      formatWorkLogLabel({ name: "Khoan cấy thép", component: "Dầm D1" }),
    ).toBe("Khoan cấy thép tại Dầm D1");
  });

  it("shows a single side unchanged", () => {
    expect(formatWorkLogLabel({ name: "Khoan cấy thép" })).toBe("Khoan cấy thép");
    expect(formatWorkLogLabel({ location: "Cọc A2" })).toBe("Cọc A2");
    expect(formatWorkLogLabel({})).toBe("");
  });
});
