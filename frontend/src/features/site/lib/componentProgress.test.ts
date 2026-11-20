import { describe, expect, it } from "vitest";
import {
  EMPTY_BULK_PROGRESS,
  EMPTY_PROGRESS_FILTERS,
  acceptanceStatusLabel,
  ambiguousStageRows,
  buildBulkProgressPayload,
  buildDesignQuantityEntries,
  bulkProgressError,
  canCommitBulkPreview,
  designQuantityValue,
  filterProgressRows,
  groupDesignQuantityEntries,
  newProgressIdempotencyKey,
  selectedProgressRows,
  sortStagesByPosition,
  stageOptionsFor,
  todayISO,
  type DesignQuantity,
  type ProgressPreview,
  type ProgressRow,
  type ProgressStage,
} from "./componentProgress";

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
    stages: [
      {
        id: "st1",
        stage_definition_id: "sd1",
        code: "PILE-REPAIR",
        name: "Sửa chữa cọc",
        position: 1,
        status: "NOT_STARTED",
        latest_event_at: null,
      },
    ],
    construction_status: "NOT_STARTED",
    construction_event: null,
    acceptance_status: "NOT_LINKED",
    acceptance_count: 0,
    acceptance_note: "Chưa có liên kết PYC/BBNT theo cấu kiện",
    stage_id: null,
    stage_available: false,
    stage_ambiguous: false,
    stage_options: [],
    ...overrides,
  };
}

it("shows a shared quantity once per work item and leaves missing values unknown", () => {
  const first = row({ canonical_code: "F-24-25" });
  const stage = first.stages[0];
  const second = row({
    id: "c2",
    canonical_code: "F-25-27",
    stages: [{ ...stage, id: "st2" }, { ...stage, id: "st3", code: "ANOTHER-WORK" }],
  });
  const quantity: DesignQuantity = {
    quantity: 29.661, unit: "kg", scope: "SHARED",
    scope_label: "F-24-25 + F-25-27", drawing: "TK-86", page: "92", note: null,
  };
  const entries = buildDesignQuantityEntries([first, second], { st1: quantity, st2: quantity, st3: quantity });
  const [shared] = groupDesignQuantityEntries(entries);
  expect(shared.items).toHaveLength(2);
  expect(shared.items[0]).toMatchObject({ quantityLabel: "29,661 kg", componentCodes: ["F-24-25", "F-25-27"] });
  expect(designQuantityValue({ ...quantity, quantity: null })).toBe("Chưa có khối lượng thiết kế");
});

describe("progress filters", () => {
  const rows = [
    row(),
    row({
      id: "c2",
      canonical_code: "I-40-42",
      raw_code: "I40-42",
      type: "beam",
      zone: "Cầu dẫn",
      segment_number: 2,
      design_group: null,
      scopes: ["ADDITIONAL_SCOPE"],
      construction_status: "COMPLETED",
      stages: [
        {
          id: "st2",
          stage_definition_id: "sd2",
          code: "BEAM-REPAIR",
          name: "Sửa chữa dầm",
          position: 1,
          status: "COMPLETED",
          latest_event_at: "2026-11-18T00:00:00+00:00",
        },
      ],
    }),
  ];

  it("returns every row unchanged for empty filters", () => {
    expect(filterProgressRows(rows, EMPTY_PROGRESS_FILTERS)).toEqual(rows);
  });

  it("filters exact values without rewriting rows", () => {
    expect(
      filterProgressRows(rows, {
        ...EMPTY_PROGRESS_FILTERS,
        query: "I-40",
      }).map((item) => item.id),
    ).toEqual(["c2"]);
    expect(
      filterProgressRows(rows, {
        ...EMPTY_PROGRESS_FILTERS,
        type: "pile",
        construction_status: "NOT_STARTED",
      }).map((item) => item.id),
    ).toEqual(["c1"]);
    expect(
      filterProgressRows(rows, {
        ...EMPTY_PROGRESS_FILTERS,
        stage_definition_id: "sd2",
        acceptance_status: "NOT_LINKED",
      }).map((item) => item.id),
    ).toEqual(["c2"]);
  });
});

describe("exact selection", () => {
  const rows = [row(), row({ id: "c2", canonical_code: "I-40-42" })];

  it("returns only rows that are really selected", () => {
    expect(selectedProgressRows(rows, ["c2", "missing"]).map((item) => item.id)).toEqual([
      "c2",
    ]);
  });
});

describe("stage ordering", () => {
  const stage = (
    id: string,
    position: number,
    code = id,
  ): ProgressStage => ({
    id,
    stage_definition_id: "sd1",
    code,
    name: `Bước ${id}`,
    position,
    status: "NOT_STARTED",
    latest_event_at: null,
  });

  it("sorts by server position, then code and id without mutating input", () => {
    const input = [
      stage("s3", 2, "B"),
      stage("s2", 1, "B"),
      stage("s1", 1, "A"),
      stage("s4", 1, "B"),
    ];
    expect(sortStagesByPosition(input).map((item) => item.id)).toEqual([
      "s1",
      "s2",
      "s4",
      "s3",
    ]);
    expect(input.map((item) => item.id)).toEqual(["s3", "s2", "s1", "s4"]);
  });

  it("keeps work selection options in the same position order", () => {
    const options = [
      stage("s3", 2, "B"),
      stage("s1", 1, "A"),
      stage("s2", 1, "B"),
    ];
    expect(
      stageOptionsFor(row({ stages: options }), "sd1").map((item) => item.id),
    ).toEqual(["s1", "s2", "s3"]);
  });
});

describe("bulk progress payload", () => {
  const draft = {
    ...EMPTY_BULK_PROGRESS,
    stage_definition_id: "sd1",
    event_date: "2026-11-18",
    status: "COMPLETED" as const,
    quantity: "1.5",
    unit: " m3 ",
    note: " đã kiểm tra ",
  };

  it("rejects missing selection, stage, date, status and bad quantity", () => {
    expect(bulkProgressError(draft, 0)).toMatch(/cấu kiện/);
    expect(bulkProgressError({ ...draft, stage_definition_id: "" }, 1)).toMatch(
      /bước/,
    );
    expect(bulkProgressError({ ...draft, event_date: "" }, 1)).toMatch(/ngày/);
    expect(bulkProgressError({ ...draft, status: "" }, 1)).toMatch(/trạng thái/);
    expect(bulkProgressError({ ...draft, quantity: "-1" }, 1)).toMatch(/Khối lượng/);
    expect(bulkProgressError({ ...draft, quantity: "abc" }, 1)).toMatch(/Khối lượng/);
  });

  it("keeps the exact selected ids and never adds evidence", () => {
    const payload = buildBulkProgressPayload(["c2", "c1"], draft);
    expect(payload.component_ids).toEqual(["c2", "c1"]);
    expect(payload.stage_definition_id).toBe("sd1");
    expect(payload.quantity).toBe(1.5);
    expect(payload.unit).toBe("m3");
    expect(payload.note).toBe("đã kiểm tra");
    expect(payload.evidence_refs).toEqual([]);
  });

  it("uses null quantity when the user leaves it blank", () => {
    expect(
      buildBulkProgressPayload(["c1"], { ...draft, quantity: "" }).quantity,
    ).toBeNull();
  });

  it("keeps explicit per-component stage selections and never guesses", () => {
    const repeated = row({
      stages: [
        {
          id: "st1",
          stage_definition_id: "sd1",
          code: "PILE-REPAIR",
          name: "Sửa chữa cọc",
          position: 1,
          repair_scope_id: "sc1",
          scope_kind: "DESIGN_SCOPE",
          status: "NOT_STARTED",
          latest_event_at: null,
        },
        {
          id: "st3",
          stage_definition_id: "sd1",
          code: "PILE-REPAIR",
          name: "Sửa chữa cọc",
          position: 1,
          repair_scope_id: "sc4",
          scope_kind: "ADDITIONAL_SCOPE",
          status: "NOT_STARTED",
          latest_event_at: null,
        },
      ],
    });
    expect(stageOptionsFor(repeated, "sd1").map((stage) => stage.id)).toEqual([
      "st1",
      "st3",
    ]);
    expect(
      ambiguousStageRows([repeated], "sd1").map((item) => item.id),
    ).toEqual(["c1"]);
    const payload = buildBulkProgressPayload(["c1"], draft, [
      { component_id: "c1", stage_id: "st3" },
      { component_id: "c2", stage_id: "st9" },
    ]);
    expect(payload.stage_selections).toEqual([
      { component_id: "c1", stage_id: "st3" },
    ]);
    expect(bulkProgressError(draft, 1, 1)).toMatch(/nhiều phạm vi/);
  });

  it("gates commit on the server preview", () => {
    const preview: ProgressPreview = {
      stage_definition_id: "sd1",
      components: [row({ stage_available: true })],
      missing_component_ids: [],
      missing_stage_component_ids: [],
      ambiguous_stage_component_ids: [],
      invalid_stage_component_ids: [],
      warnings: [],
      can_commit: true,
      count: 1,
      ready_count: 1,
    };
    expect(canCommitBulkPreview(preview)).toBe(true);
    expect(canCommitBulkPreview({ ...preview, can_commit: false })).toBe(false);
    expect(
      canCommitBulkPreview({
        ...preview,
        ambiguous_stage_component_ids: ["c1"],
      }),
    ).toBe(false);
    expect(
      canCommitBulkPreview({
        ...preview,
        invalid_stage_component_ids: ["c1"],
      }),
    ).toBe(false);
    expect(canCommitBulkPreview(null)).toBe(false);
  });

  it("keeps retry keys stable and bounded", () => {
    expect(newProgressIdempotencyKey("abc")).toBe("progress:abc");
    expect(newProgressIdempotencyKey("x".repeat(200)).length).toBe(120);
  });
});

describe("acceptance labels", () => {
  it("shows the explicit link states without inventing a result", () => {
    expect(acceptanceStatusLabel("NOT_LINKED")).toBe("Chưa liên kết");
    expect(acceptanceStatusLabel("PENDING")).toBe("Đang chờ");
    expect(acceptanceStatusLabel("APPROVED")).toBe("Đã xác nhận");
    expect(acceptanceStatusLabel("REJECTED")).toBe("Không đạt");
    expect(acceptanceStatusLabel("UNKNOWN")).toBe("UNKNOWN");
  });
});

describe("todayISO", () => {
  it("uses the Vietnam calendar day, not the device timezone", () => {
    expect(todayISO(new Date("2026-11-17T18:30:00Z"))).toBe("2026-11-18");
    expect(todayISO(new Date("2026-11-18T16:30:00Z"))).toBe("2026-11-18");
  });
});
