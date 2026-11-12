import type { WorkItem } from "../types";

export type WorkItemGroupKey =
  | "duc_pha"
  | "xu_ly_be_mat"
  | "ve_sinh_ket_dinh"
  | "khoan_cay"
  | "lap_dat_bom_vua"
  | "khac";

export type WorkItemGroup = {
  key: WorkItemGroupKey;
  label: string;
  names: string[];
};

export const WORK_ITEM_GROUPS: ReadonlyArray<{
  key: WorkItemGroupKey;
  label: string;
}> = [
  { key: "duc_pha", label: "Đục phá" },
  { key: "xu_ly_be_mat", label: "Xử lý bề mặt" },
  { key: "ve_sinh_ket_dinh", label: "Vệ sinh/kết dính" },
  { key: "khoan_cay", label: "Khoan cấy" },
  { key: "lap_dat_bom_vua", label: "Lắp đặt/bơm vữa" },
  { key: "khac", label: "Khác" },
];

/** Trim and collapse whitespace; the catalog keeps a single readable name. */
export function normalizeWorkItemName(value?: string | null): string {
  return (value ?? "").trim().replace(/\s+/g, " ");
}

/** Case/accent/spacing-insensitive key for dedupe and grouping. */
export function workItemNameKey(value: string): string {
  return normalizeWorkItemName(value)
    .toLocaleLowerCase("vi")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Classify a catalog name into the six UI groups.
 *
 * The real catalog has 41 rows but only seven unique names, so grouping is
 * keyword-based rather than dependent on a hand-maintained id list.
 */
export function workItemGroupForName(name: string): WorkItemGroupKey {
  const key = workItemNameKey(name);
  if (key.includes("duc")) return "duc_pha";
  if (key.includes("tay gi") || key.includes("xu ly be mat")) return "xu_ly_be_mat";
  if (
    key.includes("ve sinh") ||
    key.includes("keo") ||
    key.includes("epoxy") ||
    key.includes("ket dinh")
  ) {
    return "ve_sinh_ket_dinh";
  }
  if (key.includes("khoan") || key.includes("cay")) return "khoan_cay";
  if (key.includes("lap dat") || key.includes("bom vua")) {
    return "lap_dat_bom_vua";
  }
  return "khac";
}

/** Unique catalog names, preserving first-seen order and display casing. */
export function uniqueWorkItemNames(
  items: ReadonlyArray<Pick<WorkItem, "name">>,
): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const item of items) {
    const name = normalizeWorkItemName(item.name);
    if (!name) continue;
    const key = workItemNameKey(name);
    if (seen.has(key)) continue;
    seen.add(key);
    names.push(name);
  }
  return names;
}

/** Group unique names (plus any report-only names) for an `optgroup` select. */
export function groupWorkItemNames(names: ReadonlyArray<string>): WorkItemGroup[] {
  const buckets = new Map<WorkItemGroupKey, string[]>();
  const seen = new Set<string>();

  for (const rawName of names) {
    const name = normalizeWorkItemName(rawName);
    if (!name) continue;
    const key = workItemNameKey(name);
    if (seen.has(key)) continue;
    seen.add(key);
    const group = workItemGroupForName(name);
    const bucket = buckets.get(group) ?? [];
    bucket.push(name);
    buckets.set(group, bucket);
  }

  return WORK_ITEM_GROUPS.flatMap((group) => {
    const groupNames = buckets.get(group.key);
    return groupNames && groupNames.length > 0
      ? [{ ...group, names: groupNames }]
      : [];
  });
}

/**
 * Build the select options from the catalog, adding report-only names so an
 * existing `work_name` that is no longer in the catalog is still visible.
 */
export function buildWorkItemGroups(
  items: ReadonlyArray<Pick<WorkItem, "name">>,
  extraNames: ReadonlyArray<string | null | undefined> = [],
): WorkItemGroup[] {
  return groupWorkItemNames([
    ...uniqueWorkItemNames(items),
    ...extraNames.filter((name): name is string => Boolean(normalizeWorkItemName(name))),
  ]);
}

/** Map a stored work-item id to its catalog name (same project list). */
export function workItemNameById(
  items: ReadonlyArray<Pick<WorkItem, "id" | "name">>,
): Map<string, string> {
  const byId = new Map<string, string>();
  for (const item of items) {
    const name = normalizeWorkItemName(item.name);
    if (name) byId.set(item.id, name);
  }
  return byId;
}

/**
 * Export/display label: `Tên công việc tại Vị trí`.
 *
 * Location wins over component. If only one side exists, it is shown alone.
 */
export function formatWorkLogLabel(input: {
  name?: string | null;
  location?: string | null;
  component?: string | null;
}): string {
  const name = normalizeWorkItemName(input.name);
  const location = normalizeWorkItemName(input.location);
  const component = normalizeWorkItemName(input.component);
  const place = location || component;
  if (name && place) return `${name} tại ${place}`;
  return name || place;
}
