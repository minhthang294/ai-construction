/** Pure helpers and shared class tokens for the component progress panel. */

import { ApiError } from "./api";
import {
  acceptanceStatusLabel,
  buildDesignQuantityEntries,
  constructionStatusLabel,
  groupDesignQuantityEntries,
  sortStagesByPosition,
  type DesignQuantityGroup,
  type DesignQuantityMap,
  type ProgressFilters,
  type ProgressRow,
  type StageDefinition,
} from "./componentProgress";
import { resolveMainWorkStage, type MainWork } from "./mainWorks";

export type ProgressBusy = "load" | "preview" | "save" | null;

export const PROGRESS_PAGE_SIZE = 20;

export const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-600 focus-visible:ring-offset-2";

export const FIELD =
  "mt-1 min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300 sm:text-sm";

export const PRIMARY_BUTTON =
  "min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-semibold text-white active:bg-slate-900 disabled:bg-slate-300";

export const SECONDARY_BUTTON =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 active:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400";

const STATUS_CHIP: Record<string, string> = {
  NOT_STARTED: "app-status app-status--not-started",
  IN_PROGRESS: "app-status app-status--in-progress",
  COMPLETED: "app-status app-status--completed",
  BLOCKED: "app-status app-status--blocked",
};

export function statusChipClass(status: string): string {
  return STATUS_CHIP[status] ?? "app-status app-status--not-started";
}

export function acceptanceChipClass(status: string): string {
  if (status === "APPROVED" || status === "CONFIRMED") {
    return "app-acceptance-badge app-acceptance-badge--confirmed";
  }
  if (status === "REJECTED") {
    return "app-acceptance-badge app-acceptance-badge--rejected";
  }
  if (status === "PENDING" || status === "CONDITIONAL") {
    return "app-acceptance-badge app-acceptance-badge--pending";
  }
  return "app-acceptance-badge app-acceptance-badge--neutral";
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Không xác định được lỗi.";
}

export function buildActiveFilterChips(
  filters: ProgressFilters,
  definitions: ReadonlyArray<StageDefinition>,
  works: ReadonlyArray<MainWork> = [],
): string[] {
  const chips: string[] = [];
  if (filters.type) chips.push(filters.type === "pile" ? "Cọc" : "Dầm");
  if (filters.main_work_key) {
    const work = works.find((item) => item.key === filters.main_work_key);
    chips.push(work ? `${work.component_type === "pile" ? "Cọc" : "Dầm"} · ${work.label}` : "Công tác");
  }
  if (filters.construction_status) {
    chips.push(
      `Thi công: ${constructionStatusLabel(filters.construction_status)}`,
    );
  }
  if (filters.acceptance_status) {
    chips.push(
      `Nghiệm thu: ${acceptanceStatusLabel(filters.acceptance_status)}`,
    );
  }
  return chips;
}

export function countAdvancedFilters(filters: ProgressFilters): number {
  return [
    filters.type,
    filters.main_work_key,
    filters.construction_status,
    filters.acceptance_status,
  ].filter(Boolean).length;
}

export function hasProgressFilters(filters: ProgressFilters): boolean {
  return Boolean(
    filters.query.trim() ||
      filters.zone ||
      filters.segment ||
      countAdvancedFilters(filters),
  );
}

/** Segment choices, narrowed by zone and ordered by segment number. */
export function segmentOptionsFor(
  rows: ReadonlyArray<ProgressRow>,
  zone: string,
): Array<[string, number]> {
  const scopedRows = zone
    ? rows.filter((row) => row.zone === zone)
    : rows;
  return Array.from(
    new Map(
      scopedRows.map((row) => [
        String(row.segment_number),
        row.segment_number,
      ]),
    ).entries(),
  ).sort((left, right) => left[1] - right[1]);
}

/** Rows quick-code entry can match against, narrowed by zone and segment. */
export function quickCodeRowsFor(
  rows: ReadonlyArray<ProgressRow>,
  filters: ProgressFilters,
): ProgressRow[] {
  return rows.filter(
    (row) =>
      (!filters.zone || row.zone === filters.zone) &&
      (!filters.segment ||
        String(row.segment_number) === filters.segment),
  );
}

/** Definitions known from the catalog, completed from stages attached to the selection. */
export function editorDefinitionsFor(
  definitions: ReadonlyArray<StageDefinition>,
  selectedRows: ReadonlyArray<ProgressRow>,
): StageDefinition[] {
  const needed = new Set(
    selectedRows.flatMap((row) =>
      row.stages.map((stage) => stage.stage_definition_id),
    ),
  );
  const known = definitions.filter((definition) => needed.has(definition.id));
  const knownIds = new Set(known.map((definition) => definition.id));
  const derived: StageDefinition[] = [];
  for (const row of selectedRows) {
    for (const stage of row.stages) {
      if (knownIds.has(stage.stage_definition_id)) continue;
      knownIds.add(stage.stage_definition_id);
      derived.push({
        id: stage.stage_definition_id,
        type: row.type,
        code: stage.code,
        name: stage.name,
        position: stage.position,
      });
    }
  }
  return sortStagesByPosition([...known, ...derived]);
}

/** Quantity groups for the chosen main work only; unresolved scopes are left out. */
export function selectedStageQuantityGroups(
  selectedRows: ReadonlyArray<ProgressRow>,
  designQuantities: DesignQuantityMap,
  work: MainWork | null,
  stageSelections: Readonly<Record<string, string>>,
): DesignQuantityGroup[] {
  if (!work) return [];
  const stageIds = new Set(
    selectedRows
      .map((row) =>
        resolveMainWorkStage(row, work, stageSelections[row.id])?.id,
      )
      .filter((id): id is string => Boolean(id)),
  );
  return groupDesignQuantityEntries(
    buildDesignQuantityEntries(
      selectedRows,
      designQuantities,
    ).filter((entry) => stageIds.has(entry.stageId)),
  );
}

/** All stage quantities are only listed for a single selected component. */
export function allStageQuantityGroups(
  selectedRows: ReadonlyArray<ProgressRow>,
  designQuantities: DesignQuantityMap,
): DesignQuantityGroup[] {
  return selectedRows.length === 1
    ? groupDesignQuantityEntries(
        buildDesignQuantityEntries(selectedRows, designQuantities),
      )
    : [];
}
