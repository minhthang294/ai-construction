import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import {
  EMPTY_PROGRESS_FILTERS,
  type DesignQuantity,
  type ProgressRow,
  type ProgressStage,
  type StageDefinition,
} from "./componentProgress";
import type { MainWork } from "./mainWorks";
import {
  acceptanceChipClass,
  allStageQuantityGroups,
  buildActiveFilterChips,
  countAdvancedFilters,
  editorDefinitionsFor,
  errorMessage,
  hasProgressFilters,
  quickCodeRowsFor,
  segmentOptionsFor,
  selectedStageQuantityGroups,
  statusChipClass,
} from "./componentProgressPanel";

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

function quantity(overrides: Partial<DesignQuantity> = {}): DesignQuantity {
  return {
    quantity: 5,
    unit: "m3",
    scope: "COMPONENT",
    scope_label: null,
    drawing: null,
    page: null,
    note: null,
    ...overrides,
  };
}

const WORK: MainWork = {
  key: "pile-clean",
  label: "Vệ sinh bề mặt",
  component_type: "pile",
  order: 3,
  stage_definition_ids: ["sd1"],
};

describe("componentProgressPanel chips", () => {
  it("maps statuses to their badge classes and falls back to not started", () => {
    expect(statusChipClass("COMPLETED")).toBe(
      "app-status app-status--completed",
    );
    expect(statusChipClass("UNKNOWN")).toBe(
      "app-status app-status--not-started",
    );
  });

  it("groups acceptance statuses by tone", () => {
    expect(acceptanceChipClass("APPROVED")).toBe(
      "app-acceptance-badge app-acceptance-badge--confirmed",
    );
    expect(acceptanceChipClass("CONFIRMED")).toBe(
      "app-acceptance-badge app-acceptance-badge--confirmed",
    );
    expect(acceptanceChipClass("REJECTED")).toBe(
      "app-acceptance-badge app-acceptance-badge--rejected",
    );
    expect(acceptanceChipClass("PENDING")).toBe(
      "app-acceptance-badge app-acceptance-badge--pending",
    );
    expect(acceptanceChipClass("CONDITIONAL")).toBe(
      "app-acceptance-badge app-acceptance-badge--pending",
    );
    expect(acceptanceChipClass("NOT_LINKED")).toBe(
      "app-acceptance-badge app-acceptance-badge--neutral",
    );
  });

  it("returns the api or generic error message", () => {
    expect(errorMessage(new ApiError("Hỏng máy chủ", 500))).toBe(
      "Hỏng máy chủ",
    );
    expect(errorMessage(new Error("Mất mạng"))).toBe("Mất mạng");
    expect(errorMessage("lạ")).toBe("Không xác định được lỗi.");
  });
});

describe("componentProgressPanel filters", () => {
  it("describes the applied filters in display order", () => {
    expect(
      buildActiveFilterChips(
        {
          ...EMPTY_PROGRESS_FILTERS,
          type: "beam",
          main_work_key: "pile-clean",
          construction_status: "COMPLETED",
          acceptance_status: "APPROVED",
        },
        [definition()],
        [WORK],
      ),
    ).toEqual([
      "Dầm",
      "Cọc · Vệ sinh bề mặt",
      "Thi công: Hoàn thành",
      "Nghiệm thu: Đã xác nhận",
    ]);
    expect(
      buildActiveFilterChips(
        { ...EMPTY_PROGRESS_FILTERS, main_work_key: "missing" },
        [],
      ),
    ).toEqual(["Công tác"]);
  });

  it("counts advanced filters and detects active filters", () => {
    expect(countAdvancedFilters(EMPTY_PROGRESS_FILTERS)).toBe(0);
    expect(
      countAdvancedFilters({
        ...EMPTY_PROGRESS_FILTERS,
        type: "pile",
        acceptance_status: "PENDING",
      }),
    ).toBe(2);
    expect(hasProgressFilters({ ...EMPTY_PROGRESS_FILTERS, query: "   " })).toBe(
      false,
    );
    expect(hasProgressFilters({ ...EMPTY_PROGRESS_FILTERS, zone: "Cầu chính" })).toBe(
      true,
    );
    expect(
      hasProgressFilters({ ...EMPTY_PROGRESS_FILTERS, construction_status: "BLOCKED" }),
    ).toBe(true);
  });

  it("lists unique segments ordered by number, narrowed by zone", () => {
    const rows = [
      row({ segment_number: 3 }),
      row({ id: "c2", segment_number: 1 }),
      row({ id: "c3", zone: "Cầu dẫn", segment_number: 2 }),
    ];
    expect(segmentOptionsFor(rows, "")).toEqual([
      ["1", 1],
      ["2", 2],
      ["3", 3],
    ]);
    expect(segmentOptionsFor(rows, "Cầu chính")).toEqual([
      ["1", 1],
      ["3", 3],
    ]);
  });

  it("narrows quick-code candidates by zone and segment", () => {
    const rows = [
      row({ segment_number: 1 }),
      row({ id: "c2", segment_number: 2 }),
      row({ id: "c3", zone: "Cầu dẫn", segment_number: 2 }),
    ];
    expect(quickCodeRowsFor(rows, EMPTY_PROGRESS_FILTERS)).toHaveLength(3);
    expect(
      quickCodeRowsFor(rows, { ...EMPTY_PROGRESS_FILTERS, zone: "Cầu chính" }).map(
        (item) => item.id,
      ),
    ).toEqual(["c1", "c2"]);
    expect(
      quickCodeRowsFor(rows, {
        ...EMPTY_PROGRESS_FILTERS,
        zone: "Cầu chính",
        segment: "2",
      }).map((item) => item.id),
    ).toEqual(["c2"]);
  });
});

function definition(
  overrides: Partial<StageDefinition> = {},
): StageDefinition {
  return {
    id: "sd1",
    type: "pile",
    code: "PILE-REPAIR",
    name: "Sửa chữa cọc",
    position: 1,
    ...overrides,
  };
}

describe("componentProgressPanel editor definitions", () => {
  it("keeps needed catalog definitions and derives missing ones once", () => {
    const rows = [
      row({
        stages: [
          stage(),
          stage({
            id: "st2",
            stage_definition_id: "sd-new",
            code: "NEW",
            name: "Bước mới",
            position: 2,
          }),
        ],
      }),
      row({
        id: "c2",
        stages: [
          stage({
            id: "st3",
            stage_definition_id: "sd-new",
            code: "NEW",
            name: "Bước mới",
            position: 2,
          }),
        ],
      }),
    ];
    const result = editorDefinitionsFor(
      [definition(), definition({ id: "sd-unused", code: "UNUSED" })],
      rows,
    );
    expect(result.map((item) => item.id)).toEqual(["sd1", "sd-new"]);
    expect(result[1]).toEqual({
      id: "sd-new",
      type: "pile",
      code: "NEW",
      name: "Bước mới",
      position: 2,
    });
  });

  it("returns an empty list when nothing is selected", () => {
    expect(editorDefinitionsFor([definition()], [])).toEqual([]);
  });
});

describe("componentProgressPanel quantity groups", () => {
  const rows = [
    row({
      stages: [
        stage({ id: "stA", scope_kind: "DESIGN_SCOPE" }),
        stage({ id: "stB", scope_kind: "ADDITIONAL_SCOPE" }),
      ],
    }),
    row({ id: "c2", canonical_code: "I40", stages: [stage({ id: "stC" })] }),
  ];
  const quantities = {
    stA: quantity(),
    stB: quantity({ quantity: 9 }),
    stC: quantity({ quantity: 2 }),
  };

  it("returns no groups before a work is chosen", () => {
    expect(
      selectedStageQuantityGroups(rows, quantities, null, {}),
    ).toEqual([]);
  });

  it("leaves out ambiguous rows until a scope is selected", () => {
    const [group] = selectedStageQuantityGroups(rows, quantities, WORK, {});
    expect(group.items.map((item) => item.componentCodes)).toEqual([["I40"]]);
  });

  it("includes every resolved scope after selection", () => {
    const groups = selectedStageQuantityGroups(rows, quantities, WORK, {
      c1: "stA",
    });
    expect(groups.flatMap((group) => group.items)).toHaveLength(2);
    expect(
      groups.flatMap((group) => group.items).map((item) => item.quantityLabel),
    ).toEqual(["5 m3", "2 m3"]);
  });

  it("lists all stage quantities only for a single component", () => {
    expect(allStageQuantityGroups([rows[0]], quantities)).toHaveLength(1);
    expect(allStageQuantityGroups(rows, quantities)).toEqual([]);
  });
});
