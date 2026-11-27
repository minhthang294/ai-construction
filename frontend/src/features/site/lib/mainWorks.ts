/** Main construction steps and per-component resolution used by every picker. */

import { apiFetch } from "./api";
import {
  sortStagesByPosition,
  type BulkProgressDraft,
  type BulkProgressInput,
  type ProgressPreview,
  type ProgressRow,
  type ProgressSaveResult,
  type StageSelection,
} from "./componentProgress";

export type MainWork = {
  key: string;
  label: string;
  component_type: "pile" | "beam";
  order: number;
  stage_definition_ids: string[];
};

export type MainWorksCatalog = {
  works: MainWork[];
  hidden: Array<{
    id: string;
    component_type: string;
    name: string;
    reason: string;
  }>;
  unmapped: Array<{ id: string; component_type: string; name: string }>;
};

export const EMPTY_MAIN_WORKS: MainWorksCatalog = {
  works: [],
  hidden: [],
  unmapped: [],
};

export function componentTypeLabel(type: string): string {
  return type === "pile" ? "Cọc" : "Dầm";
}

export async function fetchMainWorks(
  projectId: string,
): Promise<MainWorksCatalog> {
  const res = await apiFetch(`/projects/${projectId}/main-works`);
  if (!res.ok) return EMPTY_MAIN_WORKS;
  return res.json();
}

export function mainWorkForDefinition(
  works: ReadonlyArray<MainWork>,
  stageDefinitionId: string,
): MainWork | null {
  return (
    works.find((work) =>
      work.stage_definition_ids.includes(stageDefinitionId),
    ) ?? null
  );
}

export function mainWorkByKey(
  works: ReadonlyArray<MainWork>,
  key: string,
): MainWork | null {
  return works.find((work) => work.key === key) ?? null;
}

/** Definitions of one main work as a lookup set (callers filter row stages). */
export function mainWorkDefinitionIds(work: MainWork): Set<string> {
  return new Set(work.stage_definition_ids);
}

/** Concrete stages of a component that belong to the chosen main work. */
export function stageOptionsForMainWork(
  row: ProgressRow,
  work: MainWork,
): ProgressRow["stages"] {
  const ids = mainWorkDefinitionIds(work);
  return sortStagesByPosition(
    row.stages.filter((stage) => ids.has(stage.stage_definition_id)),
  );
}

/**
 * One stage for the component, the explicit choice, or null when the
 * component has zero or several matches (the ambiguity UI takes over).
 */
export function resolveMainWorkStage(
  row: ProgressRow,
  work: MainWork,
  chosenStageId?: string | null,
): ProgressRow["stages"][number] | null {
  const options = stageOptionsForMainWork(row, work);
  if (chosenStageId) {
    return options.find((stage) => stage.id === chosenStageId) ?? null;
  }
  return options.length === 1 ? options[0] : null;
}

export function mainWorkRows(
  rows: ReadonlyArray<ProgressRow>,
  work: MainWork,
): ProgressRow[] {
  const ids = mainWorkDefinitionIds(work);
  return rows.filter((row) =>
    row.stages.some((stage) => ids.has(stage.stage_definition_id)),
  );
}

export function mainWorkChoices(works: ReadonlyArray<MainWork>): Array<{
  type: "pile" | "beam";
  label: string;
  works: MainWork[];
}> {
  return (["pile", "beam"] as const).flatMap((type) => {
    const items = works.filter((work) => work.component_type === type);
    return items.length
      ? [{ type, label: componentTypeLabel(type), works: items }]
      : [];
  });
}

/** Split resolved component stages into the per-definition lines the API takes. */
export function splitByDefinition(
  items: ReadonlyArray<{ row: ProgressRow; stageId: string }>,
): Array<{ stageDefinitionId: string; componentIds: string[]; selections: StageSelection[] }> {
  const groups = new Map<
    string,
    { componentIds: string[]; selections: StageSelection[] }
  >();
  for (const { row, stageId } of items) {
    const stage = row.stages.find((item) => item.id === stageId);
    if (!stage) continue;
    const entry =
      groups.get(stage.stage_definition_id) ??
      { componentIds: [], selections: [] };
    entry.componentIds.push(row.id);
    entry.selections.push({ component_id: row.id, stage_id: stage.id });
    groups.set(stage.stage_definition_id, entry);
  }
  return [...groups.entries()].map(([stageDefinitionId, entry]) => ({
    stageDefinitionId,
    ...entry,
  }));
}

/** Bulk input grouped by each component's own definition in the main work. */
export function splitBulkProgressPayloads(
  selectedIds: ReadonlyArray<string>,
  draft: BulkProgressDraft,
  stageSelections: Readonly<Record<string, string>>,
  rows: ReadonlyArray<ProgressRow>,
  work: MainWork | null,
): BulkProgressInput[] {
  if (!work) throw new Error("Chọn công tác trước khi gửi.");
  if (!draft.status) {
    throw new Error("Chọn trạng thái thi công trước khi gửi.");
  }
  const quantity = draft.quantity.trim()
    ? Number(draft.quantity.trim().replace(",", "."))
    : null;
  if (quantity !== null && (!Number.isFinite(quantity) || quantity < 0)) {
    throw new Error("Khối lượng phải là số không âm.");
  }
  const byId = new Map(rows.map((row) => [row.id, row]));
  const items = selectedIds.flatMap((id) => {
    const row = byId.get(id);
    const stage = row
      ? resolveMainWorkStage(row, work, stageSelections[id])
      : null;
    return row && stage ? [{ row, stageId: stage.id }] : [];
  });
  return splitByDefinition(items).map((group) => ({
    stage_definition_id: group.stageDefinitionId,
    component_ids: group.componentIds,
    stage_selections: group.selections,
    event_date: draft.event_date,
    status: draft.status as BulkProgressInput["status"],
    quantity,
    unit: draft.unit.trim() || null,
    note: draft.note.trim() || null,
    // Evidence is added from confirmed photos only; the UI does not invent it.
    evidence_refs: [],
  }));
}

export function mergeProgressPreviews(
  previews: ReadonlyArray<ProgressPreview>,
): ProgressPreview {
  function unique(values: string[]): string[] {
    return [...new Set(values)];
  }
  return {
    stage_definition_id: previews[0]?.stage_definition_id ?? "",
    components: previews.flatMap((item) => item.components),
    missing_component_ids: unique(
      previews.flatMap((item) => item.missing_component_ids),
    ),
    missing_stage_component_ids: unique(
      previews.flatMap((item) => item.missing_stage_component_ids),
    ),
    ambiguous_stage_component_ids: unique(
      previews.flatMap((item) => item.ambiguous_stage_component_ids),
    ),
    invalid_stage_component_ids: unique(
      previews.flatMap((item) => item.invalid_stage_component_ids),
    ),
    warnings: unique(previews.flatMap((item) => item.warnings)),
    can_commit: previews.length > 0 && previews.every((item) => item.can_commit),
    count: previews.reduce((total, item) => total + item.count, 0),
    ready_count: previews.reduce(
      (total, item) => total + item.ready_count,
      0,
    ),
  };
}

export function mergeProgressSaveResults(
  results: ReadonlyArray<ProgressSaveResult>,
): ProgressSaveResult {
  function unique(values: string[]): string[] {
    return [...new Set(values)];
  }
  return {
    created: results.reduce((total, item) => total + item.created, 0),
    batch_id: results[0]?.batch_id ?? "",
    events: results.flatMap((item) => item.events),
    missing_component_ids: unique(
      results.flatMap((item) => item.missing_component_ids),
    ),
    missing_stage_component_ids: unique(
      results.flatMap((item) => item.missing_stage_component_ids),
    ),
    warnings: unique(results.flatMap((item) => item.warnings)),
  };
}
