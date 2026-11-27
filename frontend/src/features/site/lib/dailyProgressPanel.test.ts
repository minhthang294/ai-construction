import { describe, expect, it } from "vitest";
import type { ComponentSegment } from "./componentImport";
import type { ProgressRow, ProgressStage, StageDefinition } from "./componentProgress";
import type { DailyProgressLineDraft, DailyProgressLinePreview } from "./dailyProgress";
import type { MainWork } from "./mainWorks";
import {
  availableWorkFor,
  definitionOptionsFor,
  lineSelectionSummary,
  previewGroupText,
  previewLineLabel,
  previewStageText,
  zonesFor,
} from "./dailyProgressPanel";

function stage(overrides: Partial<ProgressStage> = {}): ProgressStage {
  return {
    id: "st1",
    stage_definition_id: "sd1",
    code: "PILE-REPAIR",
    name: "Sửa chữa cọc",
    position: 1,
    status: "NOT_STARTED",
    latest_event_at: null,
    ...overrides,
  };
}

function row(overrides: Partial<ProgressRow> = {}): ProgressRow {
  return {
    id: "c1",
    canonical_code: "I36",
    raw_code: "I36",
    type: "pile",
    zone: "Cầu chính",
    segment_id: "s1",
    segment_number: 1,
    design_group: "Nhóm 2",
    verification: "VERIFIED",
    record_origin: "SEED_IMPORT",
    scopes: ["DESIGN_SCOPE"],
    stages: [stage()],
    construction_status: "NOT_STARTED",
    construction_event: null,
    acceptance_status: "NOT_LINKED",
    acceptance_count: 0,
    acceptance_note: "",
    stage_id: null,
    stage_available: false,
    stage_ambiguous: false,
    stage_options: [],
    ...overrides,
  };
}

function definition(overrides: Partial<StageDefinition> = {}): StageDefinition {
  return {
    id: "sd1",
    type: "pile",
    code: "PILE-REPAIR",
    name: "Sửa chữa cọc",
    position: 1,
    ...overrides,
  };
}

function line(overrides: Partial<DailyProgressLineDraft> = {}): DailyProgressLineDraft {
  return {
    main_work_key: "pile-clean",
    selected_ids: [],
    stage_selections: {},
    status: "",
    group_quantity: "",
    group_unit: "",
    ...overrides,
  };
}

function previewLine(
  overrides: Partial<DailyProgressLinePreview> = {},
): DailyProgressLinePreview {
  return {
    stage_definition_id: "sd1",
    components: [],
    missing_component_ids: [],
    missing_stage_component_ids: [],
    ambiguous_stage_component_ids: [],
    invalid_stage_component_ids: [],
    warnings: [],
    can_commit: true,
    count: 0,
    ready_count: 0,
    line_index: 0,
    stage_display_name: null,
    group_quantity: null,
    group_unit: null,
    ...overrides,
  };
}

describe("dailyProgressPanel definitions", () => {
  it("keeps the catalog list when it is present", () => {
    const definitions = [definition(), definition({ id: "sd-unused", code: "UNUSED" })];
    expect(definitionOptionsFor(definitions, [row()]).map((item) => item.id)).toEqual([
      "sd1",
      "sd-unused",
    ]);
  });

  it("derives missing definitions from rows once and sorts them", () => {
    const rows = [
      row({
        stages: [
          stage({
            id: "stB",
            stage_definition_id: "sd-b",
            code: "B",
            name: "Bước B",
            position: 5,
          }),
        ],
      }),
      row({
        id: "c2",
        stages: [
          stage({
            id: "stA",
            stage_definition_id: "sd-a",
            code: "A",
            name: "Bước A",
            position: 1,
          }),
        ],
      }),
      row({
        id: "c3",
        stages: [
          stage({
            id: "stB2",
            stage_definition_id: "sd-b",
            code: "B",
            name: "Bước B",
            position: 5,
          }),
        ],
      }),
    ];
    expect(definitionOptionsFor([], rows)).toEqual([
      { id: "sd-a", type: "pile", code: "A", name: "Bước A", position: 1 },
      { id: "sd-b", type: "pile", code: "B", name: "Bước B", position: 5 },
    ]);
  });
});

describe("dailyProgressPanel available work", () => {
  const rows = [
    row({ stages: [stage(), stage({ id: "st2", stage_definition_id: "sd2", code: "B", position: 2 })] }),
    row({
      id: "c2",
      canonical_code: "I40",
      design_group: null,
      segment_id: "s2",
      stages: [stage()],
    }),
    row({
      id: "c3",
      zone: "Cầu dẫn",
      design_group: "Nhóm 1",
      stages: [stage({ id: "st3", stage_definition_id: "sd3", code: "C", position: 3 })],
    }),
  ];
  const works: MainWork[] = [
    {
      key: "pile-clean",
      label: "Vệ sinh bề mặt",
      component_type: "pile",
      order: 3,
      stage_definition_ids: ["sd1", "sd2"],
    },
    {
      key: "beam-demolish",
      label: "Đục bê tông",
      component_type: "beam",
      order: 1,
      stage_definition_ids: ["sd3"],
    },
    {
      key: "pile-sand",
      label: "Rắc cát tạo nhám",
      component_type: "pile",
      order: 6,
      stage_definition_ids: ["sd-unused"],
    },
  ];

  it("keeps only main works with coverage inside the zone/segment filters", () => {
    const all = availableWorkFor(rows, { zone: "", segment_id: "" }, works);
    expect(all.map((item) => item.key)).toEqual(["pile-clean", "beam-demolish"]);
    expect(all.map((item) => item.count)).toEqual([2, 1]);
  });

  it("counts a component once per main work and labels by component type", () => {
    const all = availableWorkFor(rows, { zone: "", segment_id: "" }, works);
    expect(all[0].label).toBe("Cọc · Vệ sinh bề mặt (2)");
    expect(all[1].label).toBe("Dầm · Đục bê tông (1)");
  });

  it("narrows by zone and segment", () => {
    expect(
      availableWorkFor(rows, { zone: "Cầu chính", segment_id: "" }, works).map(
        (item) => item.key,
      ),
    ).toEqual(["pile-clean"]);
    expect(
      availableWorkFor(rows, { zone: "", segment_id: "s2" }, works).map(
        (item) => item.label,
      ),
    ).toEqual(["Cọc · Vệ sinh bề mặt (1)"]);
    expect(
      availableWorkFor(rows, { zone: "Cầu dẫn", segment_id: "" }, works).map(
        (item) => item.label,
      ),
    ).toEqual(["Dầm · Đục bê tông (1)"]);
  });
});

describe("dailyProgressPanel zones", () => {
  it("merges segment and row zones, drops blanks and sorts in Vietnamese", () => {
    const segments: ComponentSegment[] = [
      { id: "s1", number: 1, source_code: "S1", zone: "Cầu chính" },
      { id: "s2", number: 2, source_code: "S2", zone: "" },
    ];
    const rows = [
      row({ zone: "Cầu dẫn" }),
      row({ id: "c2", zone: "Cầu chính" }),
      row({ id: "c3", zone: "" }),
    ];
    expect(zonesFor(segments, rows)).toEqual(["Cầu chính", "Cầu dẫn"]);
  });
});

describe("dailyProgressPanel line summary", () => {
  const rows = [
    row(),
    row({ id: "c2", canonical_code: "I40" }),
    row({ id: "c3", canonical_code: "I41" }),
    row({ id: "c4", canonical_code: "I42" }),
    row({ id: "c5", canonical_code: "I43" }),
    row({ id: "c6", canonical_code: "I44" }),
  ];

  it("shows the empty status before a selection", () => {
    expect(lineSelectionSummary(line(), 2, rows)).toBe(
      "0/2 cấu kiện · Chưa chọn trạng thái",
    );
  });

  it("shows the chosen status and the selected codes", () => {
    expect(
      lineSelectionSummary(
        line({ selected_ids: ["c1", "c2"], status: "IN_PROGRESS" }),
        2,
        rows,
      ),
    ).toBe("2/2 cấu kiện · Đang thi công · I36, I40");
  });

  it("truncates after four codes and counts the rest", () => {
    expect(
      lineSelectionSummary(
        line({
          selected_ids: ["c1", "c2", "c3", "c4", "c5", "c6"],
          status: "COMPLETED",
        }),
        6,
        rows,
      ),
    ).toBe("6/6 cấu kiện · Hoàn thành · I36, I40, I41, I42 +2");
  });
});

describe("dailyProgressPanel preview text", () => {
  it("keeps a zero quantity and an absent quantity apart", () => {
    expect(previewGroupText(previewLine({ group_quantity: 5, group_unit: "m3" }))).toBe(
      "5 m3",
    );
    expect(previewGroupText(previewLine({ group_quantity: 0, group_unit: "m3" }))).toBe(
      "0 m3",
    );
    expect(previewGroupText(previewLine({ group_quantity: null, group_unit: "m3" }))).toBe(
      "m3",
    );
    expect(previewGroupText(previewLine())).toBe("");
  });

  it("prefers the server display name, then the catalog label", () => {
    expect(
      previewLineLabel(previewLine({ stage_display_name: "Tên máy chủ" }), [definition()], line()),
    ).toBe("Tên máy chủ");
    expect(previewLineLabel(previewLine(), [definition()], line())).toBe(
      "Cọc · Sửa chữa cọc (PILE-REPAIR)",
    );
    expect(previewLineLabel(previewLine(), [definition()], undefined)).toBe(
      "Cọc · Sửa chữa cọc (PILE-REPAIR)",
    );
  });

  it("labels each previewed component stage", () => {
    const chosen = stage({ id: "stA", scope_kind: "DESIGN_SCOPE" });
    expect(
      previewStageText(
        row({ stage_id: "stA", stage_options: [chosen], stage_available: true }),
      ),
    ).toBe("Thiết kế · Sửa chữa cọc");
    expect(previewStageText(row({ stage_ambiguous: true }))).toBe("Chọn phạm vi");
    expect(previewStageText(row({ stage_available: true }))).toBe(
      "Có bước thi công",
    );
    expect(previewStageText(row())).toBe("Thiếu bước");
  });
});
