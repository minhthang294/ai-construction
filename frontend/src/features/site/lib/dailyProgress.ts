/**
 * Daily progress entry: multi-line form state, exact component/stage selection
 * and the reviewed preview/save API.  Shared api.ts is not touched on purpose.
 */

import { ApiError, apiFetch } from "./api";
import type { ComponentSegment } from "./componentImport";
import {
  newProgressIdempotencyKey,
  selectedStageForRow,
  stageDefinitionLabel,
  stageOptionsFor,
  todayISO,
  type ConstructionInputStatus,
  type ProgressPreview,
  type ProgressRow,
  type ProgressSaveResult,
  type StageDefinition,
  type StageSelection,
} from "./componentProgress";

export type DailyProgressFilters = {
  zone: string;
  /** Segment id from `GET /segments`; rows compare with `segment_id`. */
  segment_id: string;
};

export const EMPTY_DAILY_PROGRESS_FILTERS: DailyProgressFilters = {
  zone: "",
  segment_id: "",
};

export type DailyProgressLineDraft = {
  stage_definition_id: string;
  selected_ids: string[];
  /** Concrete component stage id for rows with more than one matching stage. */
  stage_selections: Record<string, string>;
  status: ConstructionInputStatus | "";
  group_quantity: string;
  group_unit: string;
};

export type DailyProgressDraft = {
  event_date: string;
  lines: DailyProgressLineDraft[];
};

export type DailyProgressPayloadLine = {
  stage_definition_id: string;
  component_ids: string[];
  stage_selections?: StageSelection[];
  status: ConstructionInputStatus;
  group_quantity?: number;
  group_unit?: string;
};

export type DailyProgressPayload = {
  event_date: string;
  lines: DailyProgressPayloadLine[];
};

export type DailyProgressLinePreview = ProgressPreview & {
  line_index: number;
  group_quantity: number | null;
  group_unit: string | null;
};

export type DailyProgressPreviewResponse = {
  can_commit: boolean;
  lines: DailyProgressLinePreview[];
  warnings: string[];
};

export type DailyProgressLineResult = ProgressSaveResult & {
  line_index: number;
  stage_definition_id: string;
  group_quantity: number | null;
  group_unit: string | null;
};

export type DailyProgressSaveResponse = {
  created: number;
  lines: DailyProgressLineResult[];
};

export const MAX_DAILY_PROGRESS_LINES = 50;
export const MAX_DAILY_PROGRESS_COMPONENTS = 500;

export function newDailyProgressLine(): DailyProgressLineDraft {
  return {
    stage_definition_id: "",
    selected_ids: [],
    stage_selections: {},
    status: "",
    group_quantity: "",
    group_unit: "",
  };
}

export function createDailyProgressDraft(
  eventDate: string = todayISO(),
): DailyProgressDraft {
  return { event_date: eventDate, lines: [newDailyProgressLine()] };
}

/** Rows that actually have the chosen stage definition inside the filter. */
export function eligibleRowsForLine(
  rows: ReadonlyArray<ProgressRow>,
  stageDefinitionId: string,
  filters: DailyProgressFilters = EMPTY_DAILY_PROGRESS_FILTERS,
): ProgressRow[] {
  if (!stageDefinitionId) return [];
  return rows.filter(
    (row) =>
      (!filters.zone || row.zone === filters.zone) &&
      (!filters.segment_id || row.segment_id === filters.segment_id) &&
      stageOptionsFor(row, stageDefinitionId).length > 0,
  );
}

export function selectedStageForLineRow(
  line: DailyProgressLineDraft,
  row: ProgressRow,
) {
  return selectedStageForRow(
    row,
    line.stage_definition_id,
    line.stage_selections[row.id],
  );
}

/** Copy the prior line's ids, keeping only ids eligible for this line. */
export function copySelectionFromPriorLine(
  lines: ReadonlyArray<DailyProgressLineDraft>,
  index: number,
  eligible: ReadonlyArray<ProgressRow>,
): Pick<DailyProgressLineDraft, "selected_ids" | "stage_selections"> {
  if (index <= 0 || index >= lines.length) {
    return { selected_ids: [], stage_selections: {} };
  }
  const currentStageDefinition = lines[index].stage_definition_id;
  const prior = lines[index - 1];
  const eligibleById = new Map(eligible.map((row) => [row.id, row]));
  const selectedIds = prior.selected_ids.filter((id) =>
    eligibleById.has(id),
  );
  const stageSelections: Record<string, string> = {};
  for (const id of selectedIds) {
    const stageId = prior.stage_selections[id];
    const row = eligibleById.get(id);
    if (
      stageId &&
      row &&
      stageOptionsFor(row, currentStageDefinition).some(
        (stage) => stage.id === stageId,
      )
    ) {
      stageSelections[id] = stageId;
    }
  }
  return { selected_ids: selectedIds, stage_selections: stageSelections };
}

/** Drop any selected id that is no longer eligible after a filter change. */
export function pruneLineToEligible(
  line: DailyProgressLineDraft,
  eligible: ReadonlyArray<ProgressRow>,
): DailyProgressLineDraft {
  const eligibleIds = new Set(eligible.map((row) => row.id));
  const selectedIds = line.selected_ids.filter((id) => eligibleIds.has(id));
  const stageSelections: Record<string, string> = {};
  for (const id of selectedIds) {
    if (line.stage_selections[id]) {
      stageSelections[id] = line.stage_selections[id];
    }
  }
  return { ...line, selected_ids: selectedIds, stage_selections: stageSelections };
}

/** Clear a line whose chosen definition has no eligible work left. */
export function pruneLinesToFilters(
  lines: ReadonlyArray<DailyProgressLineDraft>,
  rows: ReadonlyArray<ProgressRow>,
  filters: DailyProgressFilters,
): DailyProgressLineDraft[] {
  return lines.map((line) => {
    if (!line.stage_definition_id) return line;
    const eligible = eligibleRowsForLine(rows, line.stage_definition_id, filters);
    if (!eligible.length) {
      return {
        ...line,
        stage_definition_id: "",
        selected_ids: [],
        stage_selections: {},
      };
    }
    return pruneLineToEligible(line, eligible);
  });
}

export function toggleDailyProgressComponent(
  line: DailyProgressLineDraft,
  componentId: string,
): DailyProgressLineDraft {
  if (line.selected_ids.includes(componentId)) {
    const stageSelections = { ...line.stage_selections };
    delete stageSelections[componentId];
    return {
      ...line,
      selected_ids: line.selected_ids.filter((id) => id !== componentId),
      stage_selections: stageSelections,
    };
  }
  return { ...line, selected_ids: [...line.selected_ids, componentId] };
}

export function updateDailyProgressLine(
  lines: ReadonlyArray<DailyProgressLineDraft>,
  index: number,
  patch: Partial<DailyProgressLineDraft>,
): DailyProgressLineDraft[] {
  return lines.map((line, lineIndex) =>
    lineIndex === index ? { ...line, ...patch } : line,
  );
}

/** Changing the stage definition clears the previous exact selection. */
export function changeLineStageDefinition(
  lines: ReadonlyArray<DailyProgressLineDraft>,
  index: number,
  stageDefinitionId: string,
): DailyProgressLineDraft[] {
  return updateDailyProgressLine(lines, index, {
    stage_definition_id: stageDefinitionId,
    selected_ids: [],
    stage_selections: {},
  });
}

export function addDailyProgressLine(
  lines: ReadonlyArray<DailyProgressLineDraft>,
): DailyProgressLineDraft[] {
  return [...lines, newDailyProgressLine()];
}

export function removeDailyProgressLine(
  lines: ReadonlyArray<DailyProgressLineDraft>,
  index: number,
): DailyProgressLineDraft[] {
  if (index < 0 || index >= lines.length) return [...lines];
  const next = lines.filter((_, lineIndex) => lineIndex !== index);
  return next.length ? next : [newDailyProgressLine()];
}

export function segmentOptionsFor(
  segments: ReadonlyArray<ComponentSegment>,
  rows: ReadonlyArray<ProgressRow>,
  zone: string,
): Array<{ id: string; number: number }> {
  const known = segments
    .filter((segment) => !zone || segment.zone === zone)
    .map((segment) => ({ id: segment.id, number: segment.number }));
  if (known.length) {
    return known.sort(
      (left, right) => left.number - right.number || left.id.localeCompare(right.id),
    );
  }
  const derived = new Map<string, number>();
  for (const row of rows) {
    if (!zone || row.zone === zone) {
      derived.set(row.segment_id, row.segment_number);
    }
  }
  return [...derived.entries()]
    .map(([id, number]) => ({ id, number }))
    .sort((left, right) => left.number - right.number || left.id.localeCompare(right.id));
}

export function dailyProgressSelectedCount(draft: DailyProgressDraft): number {
  return draft.lines.reduce((total, line) => total + line.selected_ids.length, 0);
}

function lineLabel(index: number): string {
  return `Dòng ${index + 1}`;
}

export function dailyProgressLineError(
  line: DailyProgressLineDraft,
  index: number,
  rows: ReadonlyArray<ProgressRow>,
  filters: DailyProgressFilters = EMPTY_DAILY_PROGRESS_FILTERS,
): string | null {
  const prefix = `${lineLabel(index)}: `;
  if (!line.stage_definition_id.trim()) {
    return prefix + "chọn bước thi công.";
  }
  if (line.selected_ids.length === 0) {
    return prefix + "chọn ít nhất một cấu kiện.";
  }
  const eligible = eligibleRowsForLine(rows, line.stage_definition_id, filters);
  const eligibleById = new Map(eligible.map((row) => [row.id, row]));
  for (const componentId of line.selected_ids) {
    if (!eligibleById.has(componentId)) {
      return prefix + "có cấu kiện không thuộc bước đã chọn hoặc ngoài khu/phân đoạn.";
    }
  }
  const missingStage = line.selected_ids.filter((componentId) => {
    const row = eligibleById.get(componentId);
    if (!row) return false;
    const options = stageOptionsFor(row, line.stage_definition_id);
    return options.length > 1 && !line.stage_selections[componentId];
  });
  if (missingStage.length) {
    return prefix + `chọn bước cụ thể cho ${missingStage.length} cấu kiện.`;
  }
  const invalidStage = line.selected_ids.filter((componentId) => {
    const stageId = line.stage_selections[componentId];
    if (!stageId) return false;
    const row = eligibleById.get(componentId);
    return (
      !row ||
      !stageOptionsFor(row, line.stage_definition_id).some(
        (stage) => stage.id === stageId,
      )
    );
  });
  if (invalidStage.length) {
    return prefix + "lựa chọn bước không khớp cấu kiện.";
  }
  if (!line.status) {
    return prefix + "chọn trạng thái thi công.";
  }
  if (line.group_quantity.trim()) {
    const quantity = Number(line.group_quantity.trim().replace(",", "."));
    if (!Number.isFinite(quantity) || quantity < 0 || quantity > 1e12) {
      return prefix + "khối lượng phải là số không âm.";
    }
  }
  if (line.group_unit.trim().length > 30) {
    return prefix + "đơn vị tối đa 30 ký tự.";
  }
  return null;
}

export function dailyProgressError(
  draft: DailyProgressDraft,
  rows: ReadonlyArray<ProgressRow>,
  filters: DailyProgressFilters = EMPTY_DAILY_PROGRESS_FILTERS,
  today: string = todayISO(),
): string | null {
  if (!draft.event_date) return "Chọn ngày ghi nhận.";
  if (today && draft.event_date > today) {
    return "Ngày ghi nhận không được ở tương lai.";
  }
  if (draft.lines.length === 0) return "Thêm ít nhất một dòng công việc.";
  if (draft.lines.length > MAX_DAILY_PROGRESS_LINES) {
    return `Tối đa ${MAX_DAILY_PROGRESS_LINES} dòng mỗi lần ghi.`;
  }
  if (dailyProgressSelectedCount(draft) > MAX_DAILY_PROGRESS_COMPONENTS) {
    return `Tối đa ${MAX_DAILY_PROGRESS_COMPONENTS} cấu kiện mỗi lần ghi.`;
  }
  for (let index = 0; index < draft.lines.length; index += 1) {
    const problem = dailyProgressLineError(
      draft.lines[index],
      index,
      rows,
      filters,
    );
    if (problem) return problem;
  }
  return null;
}

/** Exact selected ids and stage ids are preserved; blank extras are omitted. */
export function buildDailyProgressPayload(
  draft: DailyProgressDraft,
): DailyProgressPayload {
  return {
    event_date: draft.event_date,
    lines: draft.lines.map((line) => {
      if (!line.status) {
        throw new Error("Chọn trạng thái thi công trước khi gửi.");
      }
      const selectedIds = new Set(line.selected_ids);
      const selections = line.selected_ids.flatMap((componentId) =>
        line.stage_selections[componentId]
          ? [
              {
                component_id: componentId,
                stage_id: line.stage_selections[componentId],
              },
            ]
          : [],
      ).filter((item) => selectedIds.has(item.component_id));
      const quantity = line.group_quantity.trim()
        ? Number(line.group_quantity.trim().replace(",", "."))
        : null;
      if (quantity !== null && (!Number.isFinite(quantity) || quantity < 0 || quantity > 1e12)) {
        throw new Error("Khối lượng phải là số không âm.");
      }
      return {
        stage_definition_id: line.stage_definition_id.trim(),
        component_ids: [...line.selected_ids],
        ...(selections.length ? { stage_selections: selections } : {}),
        status: line.status,
        ...(quantity !== null ? { group_quantity: quantity } : {}),
        ...(line.group_unit.trim()
          ? { group_unit: line.group_unit.trim() }
          : {}),
      };
    }),
  };
}

export function isLinePreviewReady(line: ProgressPreview | undefined): boolean {
  return Boolean(
    line &&
      line.can_commit &&
      line.components.length > 0 &&
      line.missing_component_ids.length === 0 &&
      line.missing_stage_component_ids.length === 0 &&
      line.ambiguous_stage_component_ids.length === 0 &&
      line.invalid_stage_component_ids.length === 0,
  );
}

/** The server revalidates; the UI also refuses a partial/stale line preview. */
export function canCommitDailyProgressPreview(
  preview: DailyProgressPreviewResponse | null,
  expectedLineCount: number,
): boolean {
  return Boolean(
    preview &&
      preview.can_commit &&
      expectedLineCount > 0 &&
      preview.lines.length === expectedLineCount &&
      preview.lines.every(isLinePreviewReady),
  );
}

export function newDailyProgressIdempotencyKey(
  random?: string,
): string {
  return newProgressIdempotencyKey(random)
    .replace(/^progress:/, "daily-progress:")
    .slice(0, 120);
}

function errorMessage(body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail !== undefined) return JSON.stringify(detail) ?? "Yêu cầu thất bại.";
  return "Yêu cầu thất bại.";
}

async function readJson<T>(res: Response): Promise<T> {
  if (res.ok) return res.json();
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    // Non-JSON error body; keep the status text below.
  }
  throw new ApiError(
    body ? errorMessage(body) : `${res.status} ${res.statusText}`,
    res.status,
  );
}

export async function previewDailyProgress(
  projectId: string,
  payload: DailyProgressPayload,
): Promise<DailyProgressPreviewResponse> {
  const res = await apiFetch(`/projects/${projectId}/progress/daily-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<DailyProgressPreviewResponse>(res);
}

export async function saveDailyProgress(
  projectId: string,
  payload: DailyProgressPayload,
  idempotencyKey: string,
): Promise<DailyProgressSaveResponse> {
  const res = await apiFetch(`/projects/${projectId}/progress/daily`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...payload,
      reviewed: true,
      idempotency_key: idempotencyKey,
    }),
  });
  return readJson<DailyProgressSaveResponse>(res);
}

/** Resolve the display label from the catalog; never invent a work name. */
export function stageDefinitionLabelFor(
  definitions: ReadonlyArray<StageDefinition>,
  stageDefinitionId: string,
): string {
  const definition = definitions.find(
    (item) => item.id === stageDefinitionId,
  );
  return definition ? stageDefinitionLabel(definition) : "Bước thi công";
}
