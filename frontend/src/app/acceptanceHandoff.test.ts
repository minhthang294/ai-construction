import { describe, expect, it } from "vitest";

import { toAcceptanceInitialState } from "./acceptanceHandoff";

describe("toAcceptanceInitialState", () => {
  it("maps a paste save to the snake_case acceptance navigation payload", () => {
    expect(
      toAcceptanceInitialState({
        projectId: "p1",
        batchId: "b1",
        eventDate: "2026-11-23",
        componentIds: ["c1", "c2"],
        componentCodes: ["F1", "F2"],
        stageDefinitionIds: ["stage-1"],
      }),
    ).toEqual({
      batch_id: "b1",
      event_date: "2026-11-23",
      component_ids: ["c1", "c2"],
      stage_definition_id: "stage-1",
    });
  });

  it("uses a null stage when the saved lines span several stages", () => {
    expect(
      toAcceptanceInitialState({
        projectId: "p1",
        batchId: null,
        eventDate: "2026-11-23",
        componentIds: ["c1"],
        componentCodes: ["F1"],
        stageDefinitionIds: ["stage-1", "stage-2"],
      }),
    ).toEqual({
      batch_id: null,
      event_date: "2026-11-23",
      component_ids: ["c1"],
      stage_definition_id: null,
    });
  });
});
