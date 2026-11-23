/**
 * Handoff from the field progress flow to the acceptance screen.
 *
 * The app shell maps the saved paste request to the snake_case payload the
 * acceptance page already accepts as ``initialState``.
 */

export type AcceptanceDraftRequest = {
  projectId: string;
  batchId: string | null;
  eventDate: string;
  componentIds: string[];
  componentCodes: string[];
  stageDefinitionIds: string[];
};

export type AcceptanceInitialState = {
  batch_id: string | null;
  event_date: string;
  component_ids: string[];
  stage_definition_id: string | null;
};

export function toAcceptanceInitialState(
  request: AcceptanceDraftRequest,
): AcceptanceInitialState {
  const stages = [...new Set(request.stageDefinitionIds.filter(Boolean))];
  return {
    batch_id: request.batchId,
    event_date: request.eventDate,
    component_ids: request.componentIds,
    // A single saved stage can drive the pending list; mixed stages cannot.
    stage_definition_id: stages.length === 1 ? stages[0] : null,
  };
}
