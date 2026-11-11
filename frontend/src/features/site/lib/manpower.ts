import type { ManpowerEntry, ManpowerPreset } from "../types";

export type ManpowerSummary = {
  knownTotal: number;
  unknownGroups: string[];
  zeroGroups: string[];
  hasUnknown: boolean;
};

/**
 * Summarise manpower without collapsing `0` into `null`.
 * - `count === 0` contributes zero and is listed in `zeroGroups`.
 * - `count === null` is unknown and is listed in `unknownGroups`.
 */
export function summarizeManpower(entries: ManpowerEntry[]): ManpowerSummary {
  const known = entries.filter((entry) => entry.count !== null && entry.count !== undefined);
  const unknown = entries.filter((entry) => entry.count === null || entry.count === undefined);
  return {
    knownTotal: known.reduce((total, entry) => total + (entry.count ?? 0), 0),
    unknownGroups: unknown.map((entry) => entry.group_name),
    zeroGroups: known
      .filter((entry) => entry.count === 0)
      .map((entry) => entry.group_name),
    hasUnknown: unknown.length > 0,
  };
}

/** Convert a saved preset into a new editable manpower row without losing 0/null. */
export function presetToManpowerEntry(
  preset: Pick<
    ManpowerPreset,
    "group_name" | "person_name" | "count" | "organization_id"
  >,
): ManpowerEntry {
  return {
    group_name: preset.group_name,
    person_name: preset.person_name ?? null,
    count: preset.count ?? null,
    organization_id: preset.organization_id ?? null,
  };
}

/** Parse a manpower count input, preserving the empty string as unknown (null). */
export function parseManpowerCount(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value) || value < 0 || !Number.isInteger(value)) return null;
  return value;
}
