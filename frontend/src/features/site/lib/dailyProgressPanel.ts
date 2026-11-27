/** Pure helpers and shared class tokens for the daily progress entry panel. */

import type { ComponentSegment } from "./componentImport";
import {
  constructionStatusLabel,
  scopeLabel,
  sortStagesByPosition,
  type ProgressRow,
  type StageDefinition,
} from "./componentProgress";
import {
  stageDefinitionLabelFor,
  type DailyProgressFilters,
  type DailyProgressLineDraft,
  type DailyProgressLinePreview,
} from "./dailyProgress";
import { componentTypeLabel, type MainWork } from "./mainWorks";

export {
  FIELD,
  FOCUS_RING,
  PRIMARY_BUTTON,
  SECONDARY_BUTTON,
  statusChipClass,
} from "./componentProgressPanel";

export type DailyProgressBusy = "load" | "preview" | "save" | null;

export const DAILY_STATUS_OPTIONS = [
  { value: "IN_PROGRESS", label: "Đang thi công" },
  { value: "COMPLETED", label: "Hoàn thành" },
  { value: "BLOCKED", label: "Tạm dừng" },
] as const;

export const GROUP_UNITS = ["cọc", "dầm", "vị trí", "m", "m²", "m³", "kg", "tấn", "lít", "ca"];

export type AvailableWork = {
  key: string;
  label: string;
  type: "pile" | "beam";
  count: number;
};

/** Catalog definitions, completed from the stages attached to the loaded rows. */
export function definitionOptionsFor(
  definitions: ReadonlyArray<StageDefinition>,
  rows: ReadonlyArray<ProgressRow>,
): StageDefinition[] {
  if (definitions.length) return [...definitions];
  const derived = new Map<string, StageDefinition>();
  for (const row of rows) {
    for (const stage of row.stages) {
      if (!derived.has(stage.stage_definition_id)) {
        derived.set(stage.stage_definition_id, {
          id: stage.stage_definition_id,
          type: row.type,
          code: stage.code,
          name: stage.name,
          position: stage.position,
        });
      }
    }
  }
  return sortStagesByPosition([...derived.values()]);
}

/** Main-work choices that still have a matching component inside the filters. */
export function availableWorkFor(
  rows: ReadonlyArray<ProgressRow>,
  filters: DailyProgressFilters,
  works: ReadonlyArray<MainWork>,
): AvailableWork[] {
  const scoped = rows.filter(
    (row) =>
      (!filters.zone || row.zone === filters.zone) &&
      (!filters.segment_id || row.segment_id === filters.segment_id),
  );
  return works.flatMap((work) => {
    const ids = new Set(work.stage_definition_ids);
    const count = scoped.filter((row) =>
      row.stages.some((stage) => ids.has(stage.stage_definition_id)),
    ).length;
    if (!count) return [];
    return [{
      key: work.key,
      type: work.component_type,
      count,
      label: `${componentTypeLabel(work.component_type)} · ${work.label} (${count})`,
    }];
  });
}

/** Unique zones from segments and rows, sorted for the Vietnamese locale. */
export function zonesFor(
  segments: ReadonlyArray<ComponentSegment>,
  rows: ReadonlyArray<ProgressRow>,
): string[] {
  return Array.from(
    new Set([...segments.map((segment) => segment.zone), ...rows.map((row) => row.zone)]),
  )
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right, "vi"));
}

/** Subtitle of a collapsed line: counts, status and the first four codes. */
export function lineSelectionSummary(
  line: DailyProgressLineDraft,
  eligibleCount: number,
  rows: ReadonlyArray<ProgressRow>,
): string {
  const status = line.status
    ? constructionStatusLabel(line.status)
    : "Chưa chọn trạng thái";
  const codes = line.selected_ids
    .slice(0, 4)
    .map((id) => rows.find((row) => row.id === id)?.canonical_code ?? "")
    .filter(Boolean)
    .join(", ");
  const extra =
    line.selected_ids.length > 4
      ? ` +${line.selected_ids.length - 4}`
      : "";
  return `${line.selected_ids.length}/${eligibleCount} cấu kiện · ${status}${
    line.selected_ids.length ? ` · ${codes}${extra}` : ""
  }`;
}

/** "5 m3" when a quantity exists, otherwise the bare unit (or empty). */
export function previewGroupText(line: DailyProgressLinePreview): string {
  return line.group_quantity !== null
    ? `${line.group_quantity} ${line.group_unit ?? ""}`.trim()
    : line.group_unit ?? "";
}

/** Server display name first, then the catalog label, then the stale-line note. */
export function previewLineLabel(
  linePreview: DailyProgressLinePreview,
  definitions: ReadonlyArray<StageDefinition>,
  _line?: DailyProgressLineDraft,
): string {
  return (
    linePreview.stage_display_name ||
    stageDefinitionLabelFor(definitions, linePreview.stage_definition_id) ||
    "Đầu việc đã tách"
  );
}

/** Exact stage label for one previewed component row. */
export function previewStageText(row: ProgressRow): string {
  const chosen = row.stage_options.find((stage) => stage.id === row.stage_id);
  if (chosen) return `${scopeLabel(chosen.scope_kind)} · ${chosen.name}`;
  if (row.stage_ambiguous) return "Chọn phạm vi";
  if (row.stage_available) return "Có bước thi công";
  return "Thiếu bước";
}
