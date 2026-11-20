import { afterEach, describe, expect, it, vi } from "vitest";
import {
  EMPTY_DAILY_PROGRESS_FILTERS,
  addDailyProgressLine,
  buildDailyProgressPayload,
  canCommitDailyProgressPreview,
  changeLineStageDefinition,
  copySelectionFromPriorLine,
  createDailyProgressDraft,
  dailyProgressError,
  dailyProgressLineError,
  dailyProgressSelectedCount,
  eligibleRowsForLine,
  isLinePreviewReady,
  newDailyProgressIdempotencyKey,
  newDailyProgressLine,
  pruneLineToEligible,
  pruneLinesToFilters,
  removeDailyProgressLine,
  segmentOptionsFor,
  toggleDailyProgressComponent,
  updateDailyProgressLine,
  MAX_DAILY_PROGRESS_COMPONENTS,
  MAX_DAILY_PROGRESS_LINES,
  previewDailyProgress,
  saveDailyProgress,
  type DailyProgressLineDraft,
  type DailyProgressLinePreview,
  type DailyProgressPayload,
  type DailyProgressPreviewResponse,
} from "./dailyProgress";
import type { ProgressRow, ProgressStage } from "./componentProgress";

function stage(
  id: string,
  stageDefinitionId: string,
  overrides: Partial<ProgressStage> = {},
): ProgressStage {
  return {
    id,
    stage_definition_id: stageDefinitionId,
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
    stages: [stage("st1", "sd1")],
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

function line(
  overrides: Partial<DailyProgressLineDraft> = {},
): DailyProgressLineDraft {
  return { ...newDailyProgressLine(), ...overrides };
}

function readyPreview(
  overrides: Partial<DailyProgressLinePreview> = {},
): DailyProgressLinePreview {
  return {
    stage_definition_id: "sd1",
    components: [row({ stage_available: true, stage_id: "st1" })],
    missing_component_ids: [],
    missing_stage_component_ids: [],
    ambiguous_stage_component_ids: [],
    invalid_stage_component_ids: [],
    warnings: [],
    can_commit: true,
    count: 1,
    ready_count: 1,
    line_index: 0,
    group_quantity: null,
    group_unit: null,
    ...overrides,
  };
}

describe("eligible work", () => {
  it("keeps only rows that have the chosen stage definition inside the filter", () => {
    const rows = [
      row({ id: "c1", canonical_code: "I36" }),
      row({ id: "c2", canonical_code: "I37", stages: [stage("st2", "sd2")] }),
      row({
        id: "c3",
        canonical_code: "I38",
        zone: "Cầu phụ",
        segment_id: "s2",
        segment_number: 2,
      }),
    ];

    expect(
      eligibleRowsForLine(rows, "sd1", EMPTY_DAILY_PROGRESS_FILTERS).map(
        (item) => item.id,
      ),
    ).toEqual(["c1", "c3"]);
    expect(
      eligibleRowsForLine(rows, "sd1", { zone: "Cầu chính", segment_id: "s1" }).map(
        (item) => item.id,
      ),
    ).toEqual(["c1"]);
    expect(eligibleRowsForLine(rows, "", EMPTY_DAILY_PROGRESS_FILTERS)).toEqual([]);
  });

  it("derives segment options from rows when the segment list is empty", () => {
    const rows = [
      row({ id: "c2", segment_id: "s2", segment_number: 2 }),
      row({ id: "c1", segment_id: "s1", segment_number: 1 }),
    ];
    expect(segmentOptionsFor([], rows, "Cầu chính")).toEqual([
      { id: "s1", number: 1 },
      { id: "s2", number: 2 },
    ]);
    expect(
      segmentOptionsFor(
        [{ id: "s9", number: 9, source_code: "S9", zone: "Cầu chính" }],
        rows,
        "Cầu chính",
      ),
    ).toEqual([{ id: "s9", number: 9 }]);
  });
});

describe("selection state", () => {
  it("copies the prior line ids that remain eligible and keeps matching exact stages", () => {
    const prior = line({
      stage_definition_id: "sd1",
      selected_ids: ["c1", "c2"],
      stage_selections: { c1: "st1", c2: "st-other" },
    });
    const current = line({ stage_definition_id: "sd1" });
    const eligible = [
      row({ id: "c1", stages: [stage("st1", "sd1")] }),
      row({ id: "c3", stages: [stage("st3", "sd1")] }),
    ];

    expect(copySelectionFromPriorLine([prior, current], 1, eligible)).toEqual({
      selected_ids: ["c1"],
      stage_selections: { c1: "st1" },
    });
    expect(copySelectionFromPriorLine([prior, current], 0, eligible)).toEqual({
      selected_ids: [],
      stage_selections: {},
    });
  });

  it("toggles rows and removes their exact stage choice on deselect", () => {
    const selected = toggleDailyProgressComponent(line(), "c1");
    expect(selected.selected_ids).toEqual(["c1"]);

    const withStage = {
      ...selected,
      stage_selections: { c1: "st1" },
    };
    expect(toggleDailyProgressComponent(withStage, "c1")).toEqual({
      selected_ids: [],
      stage_selections: {},
      stage_definition_id: "",
      status: "",
      group_quantity: "",
      group_unit: "",
    });
  });

  it("changing the stage definition clears the exact selection", () => {
    const lines = [
      line({
        stage_definition_id: "sd1",
        selected_ids: ["c1"],
        stage_selections: { c1: "st1" },
      }),
    ];
    expect(changeLineStageDefinition(lines, 0, "sd2")[0]).toMatchObject({
      stage_definition_id: "sd2",
      selected_ids: [],
      stage_selections: {},
    });
  });

  it("prunes ids and stage choices after a filter change", () => {
    const pruned = pruneLineToEligible(
      line({
        stage_definition_id: "sd1",
        selected_ids: ["c1", "c2"],
        stage_selections: { c1: "st1", c2: "st2" },
      }),
      [row({ id: "c1" })],
    );
    expect(pruned.selected_ids).toEqual(["c1"]);
    expect(pruned.stage_selections).toEqual({ c1: "st1" });
  });

  it("clears a line whose stage definition has no eligible rows under the filter", () => {
    const lines = [
      line({
        stage_definition_id: "sd1",
        selected_ids: ["c1"],
        stage_selections: { c1: "st1" },
      }),
      line({ stage_definition_id: "" }),
    ];
    const pruned = pruneLinesToFilters(lines, [row({ id: "c1" })], {
      zone: "Cầu phụ",
      segment_id: "s2",
    });
    expect(pruned[0]).toMatchObject({
      stage_definition_id: "",
      selected_ids: [],
      stage_selections: {},
    });
    expect(pruned[1]).toBe(lines[1]);
  });

  it("adds, updates and keeps at least one line when removing", () => {
    const start = createDailyProgressDraft("2026-11-20");
    expect(start.lines).toHaveLength(1);

    const added = addDailyProgressLine(start.lines);
    expect(added).toHaveLength(2);
    const updated = updateDailyProgressLine(added, 1, { status: "COMPLETED" });
    expect(updated[0].status).toBe("");
    expect(updated[1].status).toBe("COMPLETED");
    expect(removeDailyProgressLine(updated, 0)).toHaveLength(1);
    expect(removeDailyProgressLine([newDailyProgressLine()], 0)).toHaveLength(1);
    expect(dailyProgressSelectedCount({
      event_date: "2026-11-20",
      lines: [
        line({ selected_ids: ["c1", "c2"] }),
        line({ selected_ids: ["c3"] }),
      ],
    })).toBe(3);
  });
});

describe("validation and payload", () => {
  it("requires a date, actual eligible work, exact stages, status and valid quantity", () => {
    const rows = [
      row({
        id: "c1",
        stages: [stage("st1", "sd1"), stage("st2", "sd1")],
      }),
    ];
    const valid = createDailyProgressDraft("2026-11-20");
    valid.lines[0] = line({
      stage_definition_id: "sd1",
      selected_ids: ["c1"],
      stage_selections: { c1: "st2" },
      status: "IN_PROGRESS",
    });

    expect(dailyProgressError(valid, rows)).toBeNull();
    expect(dailyProgressError({ ...valid, event_date: "" }, rows)).toBe(
      "Chọn ngày ghi nhận.",
    );
    expect(
      dailyProgressError(
        { ...valid, event_date: "2999-01-01" },
        rows,
        undefined,
        "2026-11-20",
      ),
    ).toBe("Ngày ghi nhận không được ở tương lai.");
    expect(
      dailyProgressError(
        {
          event_date: "2026-11-20",
          lines: Array.from({ length: MAX_DAILY_PROGRESS_LINES + 1 }, () =>
            line(),
          ),
        },
        rows,
        undefined,
        "2026-11-20",
      ),
    ).toBe(`Tối đa ${MAX_DAILY_PROGRESS_LINES} dòng mỗi lần ghi.`);
    expect(
      dailyProgressError(
        {
          event_date: "2026-11-20",
          lines: [
            line({
              selected_ids: Array.from(
                { length: MAX_DAILY_PROGRESS_COMPONENTS },
                (_, index) => `c${index}`,
              ),
            }),
            line({ selected_ids: ["extra"] }),
          ],
        },
        rows,
        undefined,
        "2026-11-20",
      ),
    ).toBe(
      `Tối đa ${MAX_DAILY_PROGRESS_COMPONENTS} cấu kiện mỗi lần ghi.`,
    );
    expect(
      dailyProgressError(
        { ...valid, lines: [line({ stage_definition_id: "sd1" })] },
        rows,
      ),
    ).toBe("Dòng 1: chọn ít nhất một cấu kiện.");
    expect(
      dailyProgressError(
        {
          ...valid,
          lines: [line({ ...valid.lines[0], stage_selections: {} })],
        },
        rows,
      ),
    ).toBe("Dòng 1: chọn bước cụ thể cho 1 cấu kiện.");
    expect(
      dailyProgressError(
        {
          ...valid,
          lines: [line({ ...valid.lines[0], stage_definition_id: "sd-other" })],
        },
        rows,
      ),
    ).toContain("không thuộc bước");
    expect(
      dailyProgressError(
        {
          ...valid,
          lines: [line({ ...valid.lines[0], status: "" })],
        },
        rows,
      ),
    ).toBe("Dòng 1: chọn trạng thái thi công.");
    expect(
      dailyProgressLineError(
        line({ ...valid.lines[0], group_quantity: "-1" }),
        0,
        rows,
      ),
    ).toBe("Dòng 1: khối lượng phải là số không âm.");
    expect(
      dailyProgressLineError(
        line({ ...valid.lines[0], group_unit: "x".repeat(31) }),
        0,
        rows,
      ),
    ).toBe("Dòng 1: đơn vị tối đa 30 ký tự.");
    expect(
      dailyProgressError(valid, rows, { zone: "Cầu phụ", segment_id: "s2" }),
    ).toContain("không thuộc bước");
  });

  it("preserves exact ids/stages and omits blank optional group values", () => {
    const draft = createDailyProgressDraft("2026-11-20");
    draft.lines = [
      line({
        stage_definition_id: "sd1",
        selected_ids: ["c1"],
        stage_selections: { c1: "st1" },
        status: "COMPLETED",
        group_quantity: " 12,5 ",
        group_unit: " m ",
      }),
      line({
        stage_definition_id: "sd2",
        selected_ids: ["c2"],
        status: "BLOCKED",
      }),
    ];

    expect(buildDailyProgressPayload(draft)).toEqual({
      event_date: "2026-11-20",
      lines: [
        {
          stage_definition_id: "sd1",
          component_ids: ["c1"],
          stage_selections: [{ component_id: "c1", stage_id: "st1" }],
          status: "COMPLETED",
          group_quantity: 12.5,
          group_unit: "m",
        },
        {
          stage_definition_id: "sd2",
          component_ids: ["c2"],
          status: "BLOCKED",
        },
      ],
    });

    expect(() =>
      buildDailyProgressPayload({
        event_date: "2026-11-20",
        lines: [line({ stage_definition_id: "sd1", selected_ids: ["c1"] })],
      }),
    ).toThrow("Chọn trạng thái thi công");
  });
});

describe("read-only preview and retry key", () => {
  it("commits only when every submitted line is ready", () => {
    const ready: DailyProgressPreviewResponse = {
      can_commit: true,
      lines: [readyPreview(), readyPreview()],
      warnings: [],
    };
    expect(canCommitDailyProgressPreview(ready, 2)).toBe(true);
    expect(canCommitDailyProgressPreview(ready, 3)).toBe(false);
    expect(
      canCommitDailyProgressPreview(
        { ...ready, lines: [readyPreview(), readyPreview()] },
        2,
      ),
    ).toBe(true);
    expect(
      canCommitDailyProgressPreview(
        {
          ...ready,
          lines: [readyPreview({ ambiguous_stage_component_ids: ["c1"] })],
        },
        1,
      ),
    ).toBe(false);
    expect(canCommitDailyProgressPreview({ ...ready, can_commit: false }, 2)).toBe(
      false,
    );
    expect(isLinePreviewReady(readyPreview({ components: [] }))).toBe(false);
    expect(canCommitDailyProgressPreview(null, 1)).toBe(false);
  });

  it("uses a bounded daily-progress idempotency key", () => {
    expect(newDailyProgressIdempotencyKey("abc")).toBe("daily-progress:abc");
    expect(newDailyProgressIdempotencyKey("x".repeat(500)).length).toBeLessThanOrEqual(
      120,
    );
    expect(newDailyProgressIdempotencyKey("x".repeat(500))).toMatch(
      /^daily-progress:/,
    );
  });
});

describe("api calls", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const payload: DailyProgressPayload = {
    event_date: "2026-11-20",
    lines: [
      {
        stage_definition_id: "sd1",
        component_ids: ["c1"],
        stage_selections: [{ component_id: "c1", stage_id: "st1" }],
        status: "COMPLETED",
        group_quantity: 0,
        group_unit: "m",
      },
    ],
  };

  function jsonResponse(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }

  it("posts the exact preview payload to the project-scoped route", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ can_commit: true, lines: [], warnings: [] }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await previewDailyProgress("p1", payload);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/projects/p1/progress/daily-preview");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual(payload);
  });

  it("adds reviewed and the idempotency key on save", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ created: 1, lines: [] }, 201));
    vi.stubGlobal("fetch", fetchMock);

    const result = await saveDailyProgress("p1", payload, "daily-progress:key");

    expect(result.created).toBe(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/projects/p1/progress/daily");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      ...payload,
      reviewed: true,
      idempotency_key: "daily-progress:key",
    });
  });

  it("surfaces the server 409 detail instead of claiming success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: "Bước thi công đã thay đổi." }, 409),
      ),
    );

    await expect(
      saveDailyProgress("p1", payload, "daily-progress:key"),
    ).rejects.toMatchObject({
      status: 409,
      message: "Bước thi công đã thay đổi.",
    });
  });
});
