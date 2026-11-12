import { describe, expect, it } from "vitest";
import type { ManpowerEntry, ManpowerPreset } from "../types";
import {
  applyManpowerPreset,
  contactNamesForRole,
  manpowerRoleForGroup,
  normalizeManpowerCount,
  normalizePersonName,
  splitManpowerTeam,
  teamToManpowerEntries,
} from "./manpowerTeam";

function preset(
  group_name: string,
  person_name: string | null,
  count: number | null = 1,
): ManpowerPreset {
  return {
    id: `${group_name}:${person_name}`,
    project_id: "p1",
    group_name,
    person_name,
    count,
    organization_id: null,
    created_at: "2026-11-12T00:00:00Z",
    updated_at: "2026-11-12T00:00:00Z",
  };
}

describe("manpower team roles", () => {
  it("recognises Vietnamese and legacy ASCII labels", () => {
    expect(manpowerRoleForGroup("Chỉ huy trưởng")).toBe("chi_huy_truong");
    expect(manpowerRoleForGroup("Chi huy truong cong truong")).toBe(
      "chi_huy_truong",
    );
    expect(manpowerRoleForGroup("Kỹ thuật")).toBe("ky_thuat");
    expect(manpowerRoleForGroup("ky thuat")).toBe("ky_thuat");
    expect(manpowerRoleForGroup("Lái xe")).toBe("lai_xe");
    expect(manpowerRoleForGroup("Bảo vệ")).toBe("bao_ve");
    expect(manpowerRoleForGroup("Công nhân")).toBe("cong_nhan");
    expect(manpowerRoleForGroup("Nhà thầu phụ")).toBeNull();
  });

  it("keeps one named chief, multiple engineers, numeric defaults and legacy rows", () => {
    const entries: ManpowerEntry[] = [
      { group_name: "Chỉ huy trưởng", person_name: "Nguyễn Văn A", count: 1 },
      { group_name: "Chỉ huy trưởng", person_name: "Người thứ hai", count: 1 },
      { group_name: "Kỹ thuật", person_name: "Trần Văn B", count: 1 },
      { group_name: "Kỹ thuật", person_name: "Lê Thị C", count: 1 },
      { group_name: "Kỹ thuật", person_name: " trần văn b ", count: 1 },
      { group_name: "Lái xe", count: null },
      { group_name: "Bảo vệ", count: 3 },
      { group_name: "Công nhân", count: 10 },
      { group_name: "Nhà thầu phụ", person_name: "Đội A", count: 7 },
    ];

    const { team, legacy } = splitManpowerTeam(entries);
    expect(team).toEqual({
      chi_huy_truong: "Nguyễn Văn A",
      ky_thuat: ["Trần Văn B", "Lê Thị C"],
      lai_xe: 0,
      bao_ve: 3,
      cong_nhan: 10,
    });
    expect(legacy.map((item) => item.group_name)).toEqual([
      "Chỉ huy trưởng",
      "Kỹ thuật",
      "Nhà thầu phụ",
    ]);
  });

  it("round-trips team plus legacy rows without collapsing explicit zero", () => {
    const legacy: ManpowerEntry[] = [
      { group_name: "Nhà thầu phụ", person_name: "Đội A", count: 7 },
    ];
    const rows = teamToManpowerEntries(
      {
        chi_huy_truong: "Nguyễn Văn A",
        ky_thuat: ["Trần Văn B", "Trần Văn B", "Lê Thị C"],
        lai_xe: 0,
        bao_ve: 2,
        cong_nhan: 10,
      },
      legacy,
    );

    expect(rows.filter((item) => item.group_name === "Chỉ huy trưởng")).toHaveLength(
      1,
    );
    expect(rows.filter((item) => item.group_name === "Kỹ thuật")).toHaveLength(2);
    expect(rows.find((item) => item.group_name === "Lái xe")?.count).toBe(0);
    expect(rows.find((item) => item.group_name === "Bảo vệ")?.count).toBe(2);
    expect(rows.find((item) => item.group_name === "Công nhân")?.count).toBe(10);
    expect(rows.at(-1)).toEqual(legacy[0]);

    const split = splitManpowerTeam(rows);
    expect(split.team.lai_xe).toBe(0);
    expect(split.legacy).toEqual([legacy[0]]);
  });

  it("applies directory presets without duplicating named roles", () => {
    const base = teamToManpowerEntries({
      chi_huy_truong: "Nguyễn Văn A",
      ky_thuat: ["Trần Văn B"],
      lai_xe: 1,
      bao_ve: 0,
      cong_nhan: 2,
    });

    const withChief = applyManpowerPreset(base, preset("Chỉ huy trưởng", "Nguyễn Văn A"));
    expect(splitManpowerTeam(withChief).team.chi_huy_truong).toBe("Nguyễn Văn A");

    const withEngineer = applyManpowerPreset(
      withChief,
      preset("Kỹ thuật", "Lê Thị C"),
    );
    expect(splitManpowerTeam(withEngineer).team.ky_thuat).toEqual([
      "Trần Văn B",
      "Lê Thị C",
    ]);

    const duplicateEngineer = applyManpowerPreset(
      withEngineer,
      preset("Kỹ thuật", "trần văn b"),
    );
    expect(splitManpowerTeam(duplicateEngineer).team.ky_thuat).toHaveLength(2);

    const driver = applyManpowerPreset(
      duplicateEngineer,
      preset("Lái xe", null, 4),
    );
    expect(splitManpowerTeam(driver).team.lai_xe).toBe(4);

    const other = applyManpowerPreset(
      driver,
      preset("Nhà thầu phụ", "Đội B", 3),
    );
    expect(splitManpowerTeam(other).legacy.map((item) => item.person_name)).toContain(
      "Đội B",
    );
  });

  it("filters and deduplicates contact picker names", () => {
    const contacts = [
      preset("Kỹ thuật", "Trần Văn B"),
      preset("Kỹ thuật", "trần văn b"),
      preset("Kỹ thuật", "Lê Thị C"),
      preset("Chỉ huy trưởng", "Nguyễn Văn A"),
      preset("Lái xe", null, 2),
    ];
    expect(contactNamesForRole(contacts, "ky_thuat")).toEqual([
      "Lê Thị C",
      "Trần Văn B",
    ]);
    expect(contactNamesForRole(contacts, "chi_huy_truong")).toEqual([
      "Nguyễn Văn A",
    ]);
  });

  it("normalises negative/fractional numeric input to a safe whole number", () => {
    expect(normalizeManpowerCount(-1)).toBe(0);
    expect(normalizeManpowerCount(1.9)).toBe(1);
    expect(normalizeManpowerCount("3")).toBe(3);
    expect(normalizeManpowerCount(Number.NaN)).toBe(0);
  });

  it("preserves spaces while typing and normalises only at the commit boundary", () => {
    const rows = teamToManpowerEntries({
      chi_huy_truong: "Nguyễn Văn ",
      ky_thuat: ["Trần  Thị "],
      lai_xe: 0,
      bao_ve: 0,
      cong_nhan: 0,
    });

    expect(rows.find((item) => item.group_name === "Chỉ huy trưởng")?.person_name).toBe(
      "Nguyễn Văn ",
    );
    expect(rows.find((item) => item.group_name === "Kỹ thuật")?.person_name).toBe(
      "Trần  Thị ",
    );

    // The controlled split round-trip must not trim the text being edited.
    const { team } = splitManpowerTeam(rows);
    expect(team.chi_huy_truong).toBe("Nguyễn Văn ");
    expect(team.ky_thuat).toEqual(["Trần  Thị "]);

    // Explicit normalisation (blur / API send) trims and collapses spaces.
    expect(normalizePersonName("  Trần   Thị  ")).toBe("Trần Thị");
    expect(normalizePersonName("   ")).toBeNull();
    expect(normalizePersonName(null)).toBeNull();
  });

  it("still deduplicates engineers after normalising their keys", () => {
    const rows = teamToManpowerEntries({
      chi_huy_truong: null,
      ky_thuat: ["Trần Văn B", " trần  văn b "],
      lai_xe: 0,
      bao_ve: 0,
      cong_nhan: 0,
    });
    expect(rows.filter((item) => item.group_name === "Kỹ thuật")).toHaveLength(1);
  });
});
