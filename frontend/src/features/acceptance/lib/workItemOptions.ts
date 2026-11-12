/**
 * PYC work-item picker helpers.
 *
 * The project catalog can repeat the same name on many rows (the real DAP
 * catalog has 41 rows but only 7 unique names, as in the daily report). The
 * PYC form therefore shows one option per name and only stores a
 * `work_item_id` when that name maps to exactly one catalog row.
 */
import type { WorkItemSummary } from "../types";

export type WorkItemOption = {
  /** `null` when several catalog rows share this name. */
  id: string | null;
  name: string;
};

/** Trim and collapse whitespace; keeps the catalog's readable casing. */
export function normalizeWorkItemName(value?: string | null): string {
  return (value ?? "").trim().replace(/\s+/g, " ");
}

/** Case/spacing-insensitive key used for grouping and lookup. */
export function workItemNameKey(value?: string | null): string {
  return normalizeWorkItemName(value).toLocaleLowerCase("vi");
}

/**
 * Collapse catalog rows into unique names, preserving first-seen order and
 * display casing. A name linked to more than one distinct id gets `id=null`
 * so a PYC is never silently attached to one arbitrary row.
 */
export function buildWorkItemOptions(
  items: ReadonlyArray<Pick<WorkItemSummary, "id" | "name">>,
): WorkItemOption[] {
  const byName = new Map<string, { name: string; ids: Set<string> }>();
  for (const item of items) {
    const name = normalizeWorkItemName(item.name);
    if (!name) continue;
    const key = workItemNameKey(name);
    const existing = byName.get(key);
    if (existing) {
      if (item.id) existing.ids.add(item.id);
      continue;
    }
    byName.set(key, {
      name,
      ids: new Set(item.id ? [item.id] : []),
    });
  }
  return [...byName.values()].map((entry) => ({
    id: entry.ids.size === 1 ? [...entry.ids][0] : null,
    name: entry.name,
  }));
}

/** Find the option whose name matches (case/whitespace-insensitive). */
export function findWorkItemOption(
  options: ReadonlyArray<WorkItemOption>,
  name?: string | null,
): WorkItemOption | null {
  const key = workItemNameKey(name);
  if (!key) return null;
  return options.find((option) => workItemNameKey(option.name) === key) ?? null;
}

/**
 * Add the PYC's current content as an option when it is not in the catalog.
 *
 * Legacy PYC rows carry free text such as "Sơn chống tia UV phạm vi dán sợi
 * cọc"; the select must still show that value instead of silently dropping it.
 */
export function withCurrentWorkItem(
  options: ReadonlyArray<WorkItemOption>,
  content?: string | null,
): WorkItemOption[] {
  const name = normalizeWorkItemName(content);
  if (!name || findWorkItemOption(options, name)) return [...options];
  return [...options, { id: null, name }];
}

/**
 * Resolve a picker selection into the PYC `content` / `work_item_id` pair.
 *
 * - empty selection: keep the current content, clear the link;
 * - catalog name: canonical name + the id only when unique;
 * - out-of-catalog value: keep the current content, clear the link.
 */
export function resolveWorkItemSelection(
  options: ReadonlyArray<WorkItemOption>,
  selectedName?: string | null,
  currentContent?: string | null,
): { content: string; work_item_id: string | null } {
  const selectedKey = workItemNameKey(selectedName);
  const current = currentContent ?? "";
  if (!selectedKey) return { content: current, work_item_id: null };
  const option = findWorkItemOption(options, selectedName);
  if (!option) return { content: current, work_item_id: null };
  return { content: option.name, work_item_id: option.id };
}
