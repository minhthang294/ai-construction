import { describe, expect, it } from "vitest";
import type { ProgressRow, ProgressStage } from "./componentProgress";
import {
  mainWorkForDefinition,
  mergeProgressPreviews,
  resolveMainWorkStage,
  splitBulkProgressPayloads,
  stageOptionsForMainWork,
  type MainWork,
} from "./mainWorks";

const WORK: MainWork = {
  key: "pile-clean",
  label: "Vệ sinh bề mặt",
  component_type: "pile",
  order: 3,
  stage_definition_ids: ["sd1", "sd2"],
};

function stage(
  id: string,
  stageDefinitionId: string,
  overrides: Partial<ProgressStage> = {},
): ProgressStage {
  return {
    id,
    stage_definition_id: stageDefinitionId,
    code: "CLEAN",
    name: "Vệ sinh",
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
    design_group: null,
    verification: "VERIFIED",
    record_origin: "SEED_IMPORT",
    scopes: ["DESIGN_SCOPE"],
    stages: [stage("st1", "sd1")],
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

describe("main work resolution", () => {
  it("finds the work containing a definition and lists its stages", () => {
    expect(mainWorkForDefinition([WORK], "sd2")?.key).toBe("pile-clean");
    expect(mainWorkForDefinition([WORK], "other")).toBeNull();
    expect(stageOptionsForMainWork(row(), WORK).map((item) => item.id)).toEqual([
      "st1",
    ]);
  });

  it("resolves one stage, honours an explicit choice, and never guesses", () => {
    expect(resolveMainWorkStage(row(), WORK)?.id).toBe("st1");
    const repeated = row({
      stages: [stage("st1", "sd1"), stage("st2", "sd1")],
    });
    expect(resolveMainWorkStage(repeated, WORK)).toBeNull();
    expect(resolveMainWorkStage(repeated, WORK, "st2")?.id).toBe("st2");
    expect(resolveMainWorkStage(repeated, WORK, "other")).toBeNull();
  });

  it("splits a bulk selection by each component's own definition", () => {
    const rows = [
      row({ id: "c1" }),
      row({ id: "c2", stages: [stage("st3", "sd2")] }),
    ];
    const payloads = splitBulkProgressPayloads(
      ["c1", "c2"],
      {
        main_work_key: WORK.key,
        event_date: "2026-11-27",
        status: "COMPLETED",
        quantity: "1,5",
        unit: " m2 ",
        note: "",
      },
      {},
      rows,
      WORK,
    );
    expect(payloads).toHaveLength(2);
    expect(payloads.map((item) => item.stage_definition_id)).toEqual([
      "sd1",
      "sd2",
    ]);
    expect(payloads.map((item) => item.component_ids)).toEqual([
      ["c1"],
      ["c2"],
    ]);
    expect(payloads[0].quantity).toBe(1.5);
    expect(payloads[0].unit).toBe("m2");
    expect(payloads[0].evidence_refs).toEqual([]);
  });

  it("merges split previews without losing any component or warning", () => {
    const merged = mergeProgressPreviews([
      {
        stage_definition_id: "sd1",
        components: [row()],
        missing_component_ids: [],
        missing_stage_component_ids: [],
        ambiguous_stage_component_ids: [],
        invalid_stage_component_ids: [],
        warnings: ["one"],
        can_commit: true,
        count: 1,
        ready_count: 1,
      },
      {
        stage_definition_id: "sd2",
        components: [row({ id: "c2" })],
        missing_component_ids: ["c9"],
        missing_stage_component_ids: [],
        ambiguous_stage_component_ids: [],
        invalid_stage_component_ids: [],
        warnings: ["one", "two"],
        can_commit: true,
        count: 2,
        ready_count: 2,
      },
    ]);
    expect(merged.count).toBe(3);
    expect(merged.ready_count).toBe(3);
    expect(merged.components.map((item) => item.id)).toEqual(["c1", "c2"]);
    expect(merged.missing_component_ids).toEqual(["c9"]);
    expect(merged.warnings).toEqual(["one", "two"]);
    expect(merged.can_commit).toBe(true);
  });
});
