/**
 * Daily progress entry: multi-line form state, exact component/stage selection
 * and the reviewed preview/save API.  Shared api.ts is not touched on purpose.
 */

import { ApiError, apiFetch } from "./api";
import type { ComponentSegment } from "./componentImport";
import {
  newProgressIdempotencyKey,
  stageDefinitionLabel,
  todayISO,
  type ConstructionInputStatus,
  type ProgressPreview,
  type ProgressRow,
  type ProgressSaveResult,
  type StageDefinition,
  type StageSelection,
} from "./componentProgress";
import {
  mainWorkDefinitionIds,
  resolveMainWorkStage,
  splitByDefinition,
  type MainWork,
} from "./mainWorks";

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
  /** Key from the project main-work catalogue; definitions resolve per row. */
  main_work_key: string;
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
  stage_display_name?: string | null;
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
    main_work_key: "",
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

/** Rows that have at least one concrete stage inside the chosen main work. */
export function eligibleRowsForLine(
  rows: ReadonlyArray<ProgressRow>,
  work: MainWork | null | undefined,
  filters: DailyProgressFilters = EMPTY_DAILY_PROGRESS_FILTERS,
): ProgressRow[] {
  if (!work) return [];
  const definitionIds = mainWorkDefinitionIds(work);
  return rows.filter(
    (row) =>
      (!filters.zone || row.zone === filters.zone) &&
      (!filters.segment_id || row.segment_id === filters.segment_id) &&
      row.stages.some((stage) =>
        definitionIds.has(stage.stage_definition_id),
      ),
  );
}

export function selectedStageForLineRow(
  line: DailyProgressLineDraft,
  row: ProgressRow,
  work: MainWork | null | undefined,
) {
  if (!work) return null;
  return resolveMainWorkStage(row, work, line.stage_selections[row.id]);
}

/** Copy the prior line's ids, keeping only ids eligible for this line. */
export function copySelectionFromPriorLine(
  lines: ReadonlyArray<DailyProgressLineDraft>,
  index: number,
  eligible: ReadonlyArray<ProgressRow>,
  work: MainWork | null | undefined,
): Pick<DailyProgressLineDraft, "selected_ids" | "stage_selections"> {
  if (index <= 0 || index >= lines.length || !work) {
    return { selected_ids: [], stage_selections: {} };
  }
  const prior = lines[index - 1];
  const eligibleById = new Map(eligible.map((row) => [row.id, row]));
  const selectedIds = prior.selected_ids.filter((id) =>
    eligibleById.has(id),
  );
  const stageSelections: Record<string, string> = {};
  for (const id of selectedIds) {
    const stageId = prior.stage_selections[id];
    const row = eligibleById.get(id);
    if (stageId && row) {
      const options = row.stages.filter(
        (stage) =>
          stage.id === stageId &&
          mainWorkDefinitionIds(work).has(stage.stage_definition_id),
      );
      if (options.length) stageSelections[id] = stageId;
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

/** Clear a line whose chosen main work has no eligible component left. */
export function pruneLinesToFilters(
  lines: ReadonlyArray<DailyProgressLineDraft>,
  rows: ReadonlyArray<ProgressRow>,
  filters: DailyProgressFilters,
  works: ReadonlyArray<MainWork>,
): DailyProgressLineDraft[] {
  return lines.map((line) => {
    if (!line.main_work_key) return line;
    const work = works.find((item) => item.key === line.main_work_key);
    const eligible = eligibleRowsForLine(rows, work, filters);
    if (!work || !eligible.length) {
      return {
        ...line,
        main_work_key: "",
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

/** Changing the main work clears the previous concrete selection. */
export function changeLineMainWork(
  lines: ReadonlyArray<DailyProgressLineDraft>,
  index: number,
  mainWorkKey: string,
): DailyProgressLineDraft[] {
  return updateDailyProgressLine(lines, index, {
    main_work_key: mainWorkKey,
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

export type DailyProgressSplit = {
  payload: DailyProgressPayload;
  /** Draft line index for each split payload line, in the same order. */
  origins: number[];
};

function resolveLineItems(
  line: DailyProgressLineDraft,
  rows: ReadonlyArray<ProgressRow>,
  work: MainWork | null,
): Array<{ row: ProgressRow; stageId: string }> {
  if (!work) return [];
  const byId = new Map(rows.map((row) => [row.id, row]));
  return line.selected_ids.flatMap((id) => {
    const row = byId.get(id);
    const stage = row
      ? resolveMainWorkStage(row, work, line.stage_selections[id])
      : null;
    return row && stage ? [{ row, stageId: stage.id }] : [];
  });
}

/**
 * Resolve each component's own stage and group by definition.  A line with one
 * resolved definition keeps its group quantity; a split line omits it rather
 * than copying the same quantity onto several stage lines.
 */
export function buildDailyProgressSplit(
  draft: DailyProgressDraft,
  rows: ReadonlyArray<ProgressRow>,
  works: ReadonlyArray<MainWork>,
): DailyProgressSplit {
  const payloadLines: DailyProgressPayloadLine[] = [];
  const origins: number[] = [];
  const seen = new Set<string>();
  draft.lines.forEach((line, lineIndex) => {
    if (!line.status) {
      throw new Error("Chọn trạng thái thi công trước khi gửi.");
    }
    const work =
      works.find((item) => item.key === line.main_work_key) ?? null;
    const items = resolveLineItems(line, rows, work);
    for (const { row, stageId } of items) {
      const key = `${row.id}|${stageId}`;
      if (seen.has(key)) {
        throw new Error("Một cấu kiện và bước thi công bị lặp giữa các dòng.");
      }
      seen.add(key);
    }
    const groups = splitByDefinition(items);
    const quantity = line.group_quantity.trim()
      ? Number(line.group_quantity.trim().replace(",", "."))
      : null;
    if (quantity !== null && (!Number.isFinite(quantity) || quantity < 0 || quantity > 1e12)) {
      throw new Error("Khối lượng phải là số không âm.");
    }
    groups.forEach((group) => {
      const single = groups.length === 1;
      payloadLines.push({
        stage_definition_id: group.stageDefinitionId,
        component_ids: group.componentIds,
        ...(group.selections.length
          ? { stage_selections: group.selections }
          : {}),
        status: line.status as ConstructionInputStatus,
        ...(single && quantity !== null ? { group_quantity: quantity } : {}),
        ...(single && line.group_unit.trim()
          ? { group_unit: line.group_unit.trim() }
          : {}),
      });
      origins.push(lineIndex);
    });
  });
  return { payload: { event_date: draft.event_date, lines: payloadLines }, origins };
}

export function dailyProgressLineError(
  line: DailyProgressLineDraft,
  index: number,
  rows: ReadonlyArray<ProgressRow>,
  filters: DailyProgressFilters = EMPTY_DAILY_PROGRESS_FILTERS,
  works: ReadonlyArray<MainWork> = [],
  seenStages: Set<string> = new Set(),
): string | null {
  const prefix = `${lineLabel(index)}: `;
  if (!line.main_work_key.trim()) {
    return prefix + "chọn công tác.";
  }
  const work = works.find((item) => item.key === line.main_work_key);
  if (!work) {
    return prefix + "công tác không còn trong danh mục.";
  }
  if (line.selected_ids.length === 0) {
    return prefix + "chọn ít nhất một cấu kiện.";
  }
  const eligible = eligibleRowsForLine(rows, work, filters);
  const eligibleById = new Map(eligible.map((row) => [row.id, row]));
  for (const componentId of line.selected_ids) {
    if (!eligibleById.has(componentId)) {
      return prefix + "có cấu kiện không thuộc công tác đã chọn hoặc ngoài khu/phân đoạn.";
    }
  }
  const missingStage = line.selected_ids.filter((componentId) => {
    const row = eligibleById.get(componentId);
    if (!row) return false;
    const options = row.stages.filter((stage) =>
      mainWorkDefinitionIds(work).has(stage.stage_definition_id),
    );
    return options.length > 1 && !line.stage_selections[componentId];
  });
  if (missingStage.length) {
    return prefix + `chọn bước cụ thể cho ${missingStage.length} cấu kiện.`;
  }
  for (const componentId of line.selected_ids) {
    const row = eligibleById.get(componentId);
    if (!row) continue;
    const chosen = line.stage_selections[componentId];
    const stage = resolveMainWorkStage(row, work, chosen);
    if (!stage) {
      return prefix + "lựa chọn bước không khớp cấu kiện.";
    }
    const key = `${row.id}|${stage.id}`;
    if (seenStages.has(key)) {
      return prefix + `cấu kiện ${row.canonical_code} bị lặp cùng bước ở dòng khác.`;
    }
    seenStages.add(key);
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
  works: ReadonlyArray<MainWork> = [],
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
  const seenStages = new Set<string>();
  for (let index = 0; index < draft.lines.length; index += 1) {
    const problem = dailyProgressLineError(
      draft.lines[index],
      index,
      rows,
      filters,
      works,
      seenStages,
    );
    if (problem) return problem;
  }
  const split = buildDailyProgressSplit(draft, rows, works);
  if (split.payload.lines.length > MAX_DAILY_PROGRESS_LINES) {
    return `Tối đa ${MAX_DAILY_PROGRESS_LINES} dòng sau khi tách theo đầu việc.`;
  }
  return null;
}

/** Split into the exact per-definition lines the existing daily API needs. */
export function buildDailyProgressPayload(
  draft: DailyProgressDraft,
  rows: ReadonlyArray<ProgressRow>,
  works: ReadonlyArray<MainWork>,
): DailyProgressPayload {
  return buildDailyProgressSplit(draft, rows, works).payload;
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
