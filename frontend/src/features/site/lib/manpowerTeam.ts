import { DEFAULT_MANPOWER_TEAM, MANPOWER_GROUPS } from "../types";
import type { ManpowerEntry, ManpowerPreset, ManpowerTeam } from "../types";
import { presetToManpowerEntry } from "./manpower";

export type ManpowerRole =
  | "chi_huy_truong"
  | "ky_thuat"
  | "lai_xe"
  | "bao_ve"
  | "cong_nhan";

const ALIASES: Record<string, ManpowerRole> = {
  "chi huy truong": "chi_huy_truong",
  "chi huy truong cong truong": "chi_huy_truong",
  "ky thuat": "ky_thuat",
  "ky thuat cong truong": "ky_thuat",
  "lai xe": "lai_xe",
  "bao ve": "bao_ve",
  "cong nhan": "cong_nhan",
};

/** Case/accent/spacing-insensitive key used to recognise legacy group labels. */
export function normalizeManpowerGroup(value?: string | null): string {
  return (value ?? "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/\s+/g, " ")
    .trim();
}

export function manpowerRoleForGroup(
  value?: string | null,
): ManpowerRole | null {
  return ALIASES[normalizeManpowerGroup(value)] ?? null;
}

export function isManagedManpowerGroup(value?: string | null): boolean {
  return manpowerRoleForGroup(value) !== null;
}

/**
 * Canonical person name used at commit boundaries (blur / API send).
 *
 * Editing state deliberately keeps the raw text so a user can type a trailing
 * space without it being swallowed on every keystroke.
 */
export function normalizePersonName(value?: string | null): string | null {
  if (value == null) return null;
  const text = value.trim().replace(/\s+/g, " ");
  return text || null;
}

function cleanName(value?: string | null): string | null {
  return normalizePersonName(value);
}

export function normalizeManpowerCount(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return 0;
  return Math.trunc(parsed);
}

export type SplitManpowerTeam = {
  team: ManpowerTeam;
  /** Rows the fixed team cannot represent, kept so old data is never lost. */
  legacy: ManpowerEntry[];
};

/**
 * Split stored manpower rows into the fixed team and free-form legacy rows.
 *
 * - the first named Chỉ huy trưởng becomes the single chief;
 * - every named Kỹ thuật becomes an engineer;
 * - Lái xe / Bảo vệ / Công nhân are numeric and default to 0;
 * - unmanaged rows and unrepresentable duplicates stay in `legacy`.
 */
export function splitManpowerTeam(entries: ManpowerEntry[]): SplitManpowerTeam {
  const team: ManpowerTeam = {
    ...DEFAULT_MANPOWER_TEAM,
    chi_huy_truong: null,
    ky_thuat: [],
  };
  const legacy: ManpowerEntry[] = [];
  const engineerNames = new Set<string>();
  const numericSeen = new Set<ManpowerRole>();
  let chiefSeen = false;

  for (const entry of entries) {
    const role = manpowerRoleForGroup(entry.group_name);
    if (!role) {
      legacy.push(entry);
      continue;
    }

    if (role === "chi_huy_truong") {
      // Keep the raw text (including a trailing space mid-typing); only the
      // dedupe/emptiness check uses the canonical form.
      const rawName = entry.person_name ?? "";
      const name = cleanName(rawName);
      if (!chiefSeen && name) {
        team.chi_huy_truong = rawName;
        chiefSeen = true;
      } else {
        legacy.push(entry);
      }
      continue;
    }

    if (role === "ky_thuat") {
      const rawName = entry.person_name ?? "";
      const name = cleanName(rawName);
      const key = name?.toLocaleLowerCase("vi");
      if (name && key && !engineerNames.has(key)) {
        engineerNames.add(key);
        team.ky_thuat.push(rawName);
      } else {
        legacy.push(entry);
      }
      continue;
    }

    if (!numericSeen.has(role)) {
      numericSeen.add(role);
      team[role] = normalizeManpowerCount(entry.count);
    } else {
      legacy.push(entry);
    }
  }

  return { team, legacy };
}

/** Build the canonical manpower rows the existing API/schema already stores. */
export function teamToManpowerEntries(
  team: ManpowerTeam,
  legacy: ManpowerEntry[] = [],
): ManpowerEntry[] {
  const result: ManpowerEntry[] = [];
  const rawChief = team.chi_huy_truong ?? "";
  if (cleanName(rawChief)) {
    result.push({
      group_name: MANPOWER_GROUPS.chief,
      // Preserve the raw editing value; normalize on blur / before API send.
      person_name: rawChief,
      count: 1,
    });
  }

  const engineerNames = new Set<string>();
  for (const rawName of team.ky_thuat) {
    const name = cleanName(rawName);
    const key = name?.toLocaleLowerCase("vi");
    if (!name || !key || engineerNames.has(key)) continue;
    engineerNames.add(key);
    result.push({
      group_name: MANPOWER_GROUPS.technical,
      person_name: rawName,
      count: 1,
    });
  }

  result.push({
    group_name: MANPOWER_GROUPS.driver,
    person_name: null,
    count: normalizeManpowerCount(team.lai_xe),
  });
  result.push({
    group_name: MANPOWER_GROUPS.guard,
    person_name: null,
    count: normalizeManpowerCount(team.bao_ve),
  });
  result.push({
    group_name: MANPOWER_GROUPS.worker,
    person_name: null,
    count: normalizeManpowerCount(team.cong_nhan),
  });

  return [...result, ...legacy.map((entry) => ({ ...entry }))];
}

/** Unique directory names for one named role, sorted for a stable picker. */
export function contactNamesForRole(
  contacts: Array<Pick<ManpowerPreset, "group_name" | "person_name">>,
  role: "chi_huy_truong" | "ky_thuat",
): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const contact of contacts) {
    if (manpowerRoleForGroup(contact.group_name) !== role) continue;
    const name = cleanName(contact.person_name);
    const key = name?.toLocaleLowerCase("vi");
    if (!name || !key || seen.has(key)) continue;
    seen.add(key);
    names.push(name);
  }
  return names.sort((a, b) => a.localeCompare(b, "vi"));
}

/**
 * Apply a saved directory preset without creating duplicate fixed-role rows.
 * Numeric presets update the matching count; unknown groups remain free-form.
 */
export function applyManpowerPreset(
  entries: ManpowerEntry[],
  preset: ManpowerPreset,
): ManpowerEntry[] {
  const { team, legacy } = splitManpowerTeam(entries);
  const role = manpowerRoleForGroup(preset.group_name);
  const name = cleanName(preset.person_name);

  if (role === "chi_huy_truong" && name) {
    team.chi_huy_truong = name;
  } else if (role === "ky_thuat" && name) {
    const key = name.toLocaleLowerCase("vi");
    if (!team.ky_thuat.some((item) => item.toLocaleLowerCase("vi") === key)) {
      team.ky_thuat.push(name);
    }
  } else if (role && role !== "chi_huy_truong" && role !== "ky_thuat") {
    team[role] = normalizeManpowerCount(preset.count);
  } else {
    legacy.push(presetToManpowerEntry(preset));
  }

  return teamToManpowerEntries(team, legacy);
}
