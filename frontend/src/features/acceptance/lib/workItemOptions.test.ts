import { describe, expect, it } from "vitest";
import {
  buildWorkItemOptions,
  findWorkItemOption,
  resolveWorkItemSelection,
  withCurrentWorkItem,
  workItemNameKey,
} from "./workItemOptions";

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

describe("buildWorkItemOptions", () => {
  it("collapses 41 catalog rows into seven unique name options", () => {
    const options = buildWorkItemOptions(catalogRows());
    expect(options).toHaveLength(7);
    expect(options.map((option) => option.name)).toEqual(CATALOG_NAMES);
  });

  it("keeps the id when a name belongs to exactly one work item", () => {
    const options = buildWorkItemOptions([
      { id: "w-khoan", name: "Khoan cấy thép" },
      { id: "w-duc-1", name: "Đục bỏ bê tông om vỡ" },
    ]);
    expect(findWorkItemOption(options, "Khoan cấy thép")).toEqual({
      id: "w-khoan",
      name: "Khoan cấy thép",
    });
    expect(options).toEqual([
      { id: "w-khoan", name: "Khoan cấy thép" },
      { id: "w-duc-1", name: "Đục bỏ bê tông om vỡ" },
    ]);
  });

  it("sets id=null when several work items share the same name", () => {
    const options = buildWorkItemOptions([
      { id: "w1", name: "Khoan cấy thép" },
      { id: "w2", name: "Khoan cấy thép" },
    ]);
    expect(options).toEqual([{ id: null, name: "Khoan cấy thép" }]);
  });

  it("normalises whitespace and case before grouping", () => {
    const options = buildWorkItemOptions([
      { id: "w1", name: "  Khoan   cấy thép " },
      { id: "w2", name: "khoan cấy thép" },
      { id: "w3", name: "KHOAN CẤY THÉP" },
    ]);
    expect(options).toHaveLength(1);
    expect(options[0]).toEqual({ id: null, name: "Khoan cấy thép" });
    expect(workItemNameKey("  KHOAN   CẤY THÉP ")).toBe("khoan cấy thép");
  });

  it("ignores blank names and keeps the same id from being counted twice", () => {
    const options = buildWorkItemOptions([
      { id: "w1", name: "Khoan cấy thép" },
      { id: "w1", name: "Khoan cấy thép" },
      { id: "w2", name: "   " },
    ]);
    expect(options).toEqual([{ id: "w1", name: "Khoan cấy thép" }]);
  });
});

describe("PYC content selection", () => {
  it("resolves a unique catalog name to canonical content and id", () => {
    const options = buildWorkItemOptions([
      { id: "w-khoan", name: "Khoan cấy thép" },
      { id: "w-duc", name: "Đục bỏ bê tông om vỡ" },
    ]);
    expect(
      resolveWorkItemSelection(options, "  khoan   CẤY THÉP ", "old"),
    ).toEqual({ content: "Khoan cấy thép", work_item_id: "w-khoan" });
  });

  it("clears the id for a duplicated name", () => {
    const options = buildWorkItemOptions([
      { id: "w1", name: "Khoan cấy thép" },
      { id: "w2", name: "Khoan cấy thép" },
    ]);
    expect(resolveWorkItemSelection(options, "Khoan cấy thép", "old")).toEqual({
      content: "Khoan cấy thép",
      work_item_id: null,
    });
  });

  it("keeps the existing PYC content outside the catalog", () => {
    const options = buildWorkItemOptions([{ id: "w1", name: "Khoan cấy thép" }]);
    const legacy = "Sơn chống tia UV phạm vi dán sợi cọc";

    expect(withCurrentWorkItem(options, legacy)).toEqual([
      { id: "w1", name: "Khoan cấy thép" },
      { id: null, name: legacy },
    ]);
    expect(resolveWorkItemSelection(options, legacy, legacy)).toEqual({
      content: legacy,
      work_item_id: null,
    });
  });

  it("clears the link when the user clears the picker but keeps the typed content", () => {
    const options = buildWorkItemOptions([{ id: "w1", name: "Khoan cấy thép" }]);
    expect(resolveWorkItemSelection(options, "", "Nội dung tự nhập")).toEqual({
      content: "Nội dung tự nhập",
      work_item_id: null,
    });
  });
});
