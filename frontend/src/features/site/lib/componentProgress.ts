/** Types and pure helpers for component progress and reviewed bulk updates. */

export type ConstructionStatus =
  | "NOT_STARTED"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "BLOCKED";
export type ConstructionInputStatus = "IN_PROGRESS" | "COMPLETED" | "BLOCKED";
export type AcceptanceStatus =
  | "NOT_LINKED"
  | "PENDING"
  | "APPROVED"
  | "CONDITIONAL"
  | "REJECTED"
  | "CONFIRMED";

export type ProgressStage = {
  id: string;
  stage_definition_id: string;
  code: string;
  name: string;
  position: number;
  repair_scope_id?: string | null;
  scope_kind?: string | null;
  status: ConstructionStatus;
  latest_event_at: string | null;
};

export type ProgressLatestEvent = {
  id: string;
  stage_id: string;
  stage_code: string | null;
  stage_name: string | null;
  event_date: string;
  status: ConstructionStatus;
  quantity: number | null;
  unit: string | null;
  note: string | null;
  created_at: string;
};

/** Exact response of `GET /projects/{p}/progress`. */
export type ProgressRow = {
  id: string;
  canonical_code: string;
  raw_code: string;
  type: "pile" | "beam";
  zone: string;
  segment_id: string;
  segment_number: number;
  design_group: string | null;
  verification: string;
  record_origin: string;
  scopes: string[];
  stages: ProgressStage[];
  construction_status: ConstructionStatus;
  construction_event: ProgressLatestEvent | null;
  acceptance_status: AcceptanceStatus;
  acceptance_count: number;
  acceptance_note: string;
  stage_id: string | null;
  stage_available: boolean;
  stage_ambiguous: boolean;
  stage_options: ProgressStage[];
};

export type StageDefinition = {
  id: string;
  type: "pile" | "beam";
  code: string;
  name: string;
  position: number;
};

export type ProgressFilters = {
  query: string;
  zone: string;
  segment: string;
  type: string;
  stage_definition_id: string;
  construction_status: string;
  acceptance_status: string;
};

export const EMPTY_PROGRESS_FILTERS: ProgressFilters = {
  query: "",
  zone: "",
  segment: "",
  type: "",
  stage_definition_id: "",
  construction_status: "",
  acceptance_status: "",
};

export type BulkProgressDraft = {
  stage_definition_id: string;
  event_date: string;
  status: ConstructionInputStatus | "";
  quantity: string;
  unit: string;
  note: string;
};

export const EMPTY_BULK_PROGRESS: BulkProgressDraft = {
  stage_definition_id: "",
  event_date: "",
  status: "",
  quantity: "",
  unit: "",
  note: "",
};

export type StageSelection = {
  component_id: string;
  stage_id: string;
};

export type BulkProgressInput = {
  stage_definition_id: string;
  component_ids: string[];
  stage_selections: StageSelection[];
  event_date: string;
  status: ConstructionInputStatus;
  quantity: number | null;
  unit: string | null;
  note: string | null;
  evidence_refs: string[];
};

export type ProgressPreview = {
  stage_definition_id: string;
  components: ProgressRow[];
  missing_component_ids: string[];
  missing_stage_component_ids: string[];
  ambiguous_stage_component_ids: string[];
  invalid_stage_component_ids: string[];
  warnings: string[];
  can_commit: boolean;
  count: number;
  ready_count: number;
};

export type ProgressEvent = {
  id: string;
  component_id: string;
  stage_id: string;
  event_date: string;
  status: ConstructionStatus;
  quantity: number | null;
  unit: string | null;
  note: string | null;
  evidence_refs: string[];
  created_at: string;
};

export type ProgressSaveResult = {
  created: number;
  batch_id: string;
  events: ProgressEvent[];
  missing_component_ids: string[];
  missing_stage_component_ids: string[];
  warnings: string[];
};

export type DesignQuantityScope = "COMPONENT" | "SHARED" | "SUBGROUP";

/** Read-only design quantity keyed by concrete stage ID. */
export type DesignQuantity = {
  quantity: number | null;
  unit: string | null;
  scope: DesignQuantityScope;
  scope_label: string | null;
  drawing: string | null;
  page: string | null;
  note: string | null;
};

export type DesignQuantityMap = Record<string, DesignQuantity>;

export type DesignQuantityEntry = {
  stageId: string;
  componentId: string;
  componentCode: string;
  stageCode: string;
  stageName: string;
  value: DesignQuantity;
};

export type DesignQuantityItem = {
  key: string;
  scope: DesignQuantityScope;
  scopeLabel: string;
  quantityLabel: string;
  drawing: string | null;
  page: string | null;
  note: string | null;
  componentCodes: string[];
  stageNames: string[];
};

export type DesignQuantityGroup = {
  scope: DesignQuantityScope;
  label: string;
  items: DesignQuantityItem[];
};

const DESIGN_QUANTITY_SCOPE_LABELS: Record<DesignQuantityScope, string> = {
  COMPONENT: "Theo mã cấu kiện",
  SHARED: "Dùng chung",
  SUBGROUP: "Theo nhóm",
};
const DESIGN_QUANTITY_NUMBER = new Intl.NumberFormat("vi-VN", {
  maximumFractionDigits: 10,
});

export function designQuantityScopeLabel(scope: DesignQuantityScope): string {
  return DESIGN_QUANTITY_SCOPE_LABELS[scope] ?? scope;
}

export const CONSTRUCTION_STATUS_LABELS: Record<ConstructionStatus, string> = {
  NOT_STARTED: "Chưa bắt đầu",
  IN_PROGRESS: "Đang thi công",
  COMPLETED: "Hoàn thành",
  BLOCKED: "Tạm dừng",
};

export function constructionStatusLabel(status: string): string {
  return (
    CONSTRUCTION_STATUS_LABELS[status as ConstructionStatus] ?? status
  );
}

export const ACCEPTANCE_STATUS_LABELS: Record<AcceptanceStatus, string> = {
  NOT_LINKED: "Chưa liên kết",
  PENDING: "Đang chờ",
  APPROVED: "Đã xác nhận",
  CONDITIONAL: "Có điều kiện",
  REJECTED: "Không đạt",
  CONFIRMED: "Đã xác nhận",
};

export function acceptanceStatusLabel(status: string): string {
  return (
    ACCEPTANCE_STATUS_LABELS[status as AcceptanceStatus] ?? status
  );
}

export function stageDefinitionLabel(definition: StageDefinition): string {
  return `${definition.type === "pile" ? "Cọc" : "Dầm"} · ${definition.name} (${definition.code})`;
}

export function scopeLabel(scopeKind?: string | null): string {
  if (scopeKind === "ADDITIONAL_SCOPE") return "Phát sinh";
  if (scopeKind === "DESIGN_SCOPE") return "Thiết kế";
  return "Phạm vi";
}

export function stageOptionsFor(
  row: ProgressRow,
  stageDefinitionId: string,
): ProgressStage[] {
  if (!stageDefinitionId) return [];
  return row.stages.filter(
    (stage) => stage.stage_definition_id === stageDefinitionId,
  );
}

/** Selected components with more than one stage for the chosen definition. */
export function ambiguousStageRows(
  rows: ReadonlyArray<ProgressRow>,
  stageDefinitionId: string,
): ProgressRow[] {
  return rows.filter(
    (row) => stageOptionsFor(row, stageDefinitionId).length > 1,
  );
}

/** The concrete stage the user chose, or the only option; never guesses among several. */
export function selectedStageForRow(
  row: ProgressRow,
  stageDefinitionId: string,
  selectedStageId?: string | null,
): ProgressStage | null {
  const options = stageOptionsFor(row, stageDefinitionId);
  if (selectedStageId) {
    return options.find((stage) => stage.id === selectedStageId) ?? null;
  }
  return options.length === 1 ? options[0] : null;
}

export function designQuantityForStage(
  quantities: DesignQuantityMap | null | undefined,
  stageId: string | null | undefined,
): DesignQuantity | null {
  if (!stageId) return null;
  return quantities?.[stageId] ?? null;
}

/** A missing or null quantity is unavailable, never zero. */
export function designQuantityValue(
  value: DesignQuantity | null | undefined,
): string {
  if (
    !value ||
    typeof value.quantity !== "number" ||
    !Number.isFinite(value.quantity)
  ) {
    return "Chưa có khối lượng thiết kế";
  }
  const amount = DESIGN_QUANTITY_NUMBER.format(value.quantity);
  return value.unit?.trim() ? `${amount} ${value.unit.trim()}` : amount;
}

/** Flatten resolved stage quantities; absent stages are left out, not zeroed. */
export function buildDesignQuantityEntries(
  rows: ReadonlyArray<ProgressRow>,
  quantities: DesignQuantityMap,
  stageDefinitionId?: string,
): DesignQuantityEntry[] {
  const entries: DesignQuantityEntry[] = [];
  for (const row of rows) {
    for (const stage of row.stages) {
      if (
        stageDefinitionId &&
        stage.stage_definition_id !== stageDefinitionId
      ) {
        continue;
      }
      const value = designQuantityForStage(quantities, stage.id);
      if (!value) continue;
      entries.push({
        stageId: stage.id,
        componentId: row.id,
        componentCode: row.canonical_code,
        stageCode: stage.code,
        stageName: stage.name,
        value,
      });
    }
  }
  return entries;
}

function designQuantityItemKey(entry: DesignQuantityEntry): string {
  const value = entry.value;
  if (value.scope === "COMPONENT") {
    return `COMPONENT|${entry.componentId}|${entry.stageId}`;
  }
  return [
    value.scope,
    entry.stageCode,
    value.scope_label ?? "",
    value.drawing ?? "",
    value.page ?? "",
    value.note ?? "",
    value.quantity ?? "",
    value.unit ?? "",
  ].join("|");
}

/**
 * Keep per-code values distinct; dedupe shared/subgroup values by scope metadata.
 * Values are never summed or merged into a total.
 */
export function groupDesignQuantityEntries(
  entries: ReadonlyArray<DesignQuantityEntry>,
): DesignQuantityGroup[] {
  const groups: Record<DesignQuantityScope, DesignQuantityItem[]> = {
    COMPONENT: [],
    SHARED: [],
    SUBGROUP: [],
  };
  const index = new Map<string, DesignQuantityItem>();
  for (const entry of entries) {
    const key = designQuantityItemKey(entry);
    let item = index.get(key);
    if (!item) {
      item = {
        key,
        scope: entry.value.scope,
        scopeLabel:
          entry.value.scope_label?.trim() ||
          designQuantityScopeLabel(entry.value.scope),
        quantityLabel: designQuantityValue(entry.value),
        drawing: entry.value.drawing,
        page: entry.value.page,
        note: entry.value.note,
        componentCodes: [],
        stageNames: [],
      };
      index.set(key, item);
      groups[entry.value.scope]?.push(item);
    }
    if (!item.componentCodes.includes(entry.componentCode)) {
      item.componentCodes.push(entry.componentCode);
    }
    if (!item.stageNames.includes(entry.stageName)) {
      item.stageNames.push(entry.stageName);
    }
  }
  return (["COMPONENT", "SHARED", "SUBGROUP"] as const)
    .map((scope) => ({
      scope,
      label: designQuantityScopeLabel(scope),
      items: groups[scope],
    }))
    .filter((group) => group.items.length > 0);
}

export function selectionsForSelected(
  selectedIds: ReadonlyArray<string>,
  selections: Readonly<Record<string, string>>,
): StageSelection[] {
  return selectedIds.flatMap((componentId) =>
    selections[componentId]
      ? [{ component_id: componentId, stage_id: selections[componentId] }]
      : [],
  );
}

function searchable(row: ProgressRow): string {
  return [
    row.canonical_code,
    row.raw_code,
    row.zone,
    row.design_group ?? "",
    ...row.stages.map((stage) => `${stage.code} ${stage.name}`),
  ]
    .join(" ")
    .toLowerCase();
}

/** Filter for display; values are not rewritten. */
export function filterProgressRows(
  rows: ReadonlyArray<ProgressRow>,
  filters: ProgressFilters,
): ProgressRow[] {
  const query = filters.query.trim().toLowerCase();
  return rows.filter((row) => {
    if (filters.zone && row.zone !== filters.zone) return false;
    if (filters.segment && String(row.segment_number) !== filters.segment) {
      return false;
    }
    if (filters.type && row.type !== filters.type) return false;
    if (
      filters.stage_definition_id &&
      !row.stages.some(
        (stage) => stage.stage_definition_id === filters.stage_definition_id,
      )
    ) {
      return false;
    }
    if (
      filters.construction_status &&
      row.construction_status !== filters.construction_status
    ) {
      return false;
    }
    if (
      filters.acceptance_status &&
      row.acceptance_status !== filters.acceptance_status
    ) {
      return false;
    }
    return !query || searchable(row).includes(query);
  });
}

/** Only rows actually present are returned; ids are never expanded or guessed. */
export function selectedProgressRows(
  rows: ReadonlyArray<ProgressRow>,
  selectedIds: ReadonlyArray<string>,
): ProgressRow[] {
  const wanted = new Set(selectedIds);
  return rows.filter((row) => wanted.has(row.id));
}

export function bulkProgressError(
  draft: BulkProgressDraft,
  selectedCount: number,
  missingStageChoiceCount = 0,
): string | null {
  if (selectedCount === 0) return "Chọn ít nhất một cấu kiện.";
  if (!draft.stage_definition_id.trim()) return "Chọn bước thi công.";
  if (missingStageChoiceCount > 0) {
    return `Chọn bước cụ thể cho ${missingStageChoiceCount} cấu kiện có nhiều phạm vi.`;
  }
  if (!draft.event_date) return "Chọn ngày ghi nhận.";
  if (!draft.status) return "Chọn trạng thái thi công.";
  if (draft.quantity.trim()) {
    const value = Number(draft.quantity);
    if (!Number.isFinite(value) || value < 0) {
      return "Khối lượng phải là số không âm.";
    }
  }
  if (draft.unit.trim().length > 30) return "Đơn vị tối đa 30 ký tự.";
  if (draft.note.trim().length > 2000) return "Ghi chú tối đa 2000 ký tự.";
  return null;
}

/** Payload for preview and save; the exact selected ids/stages are preserved. */
export function buildBulkProgressPayload(
  selectedIds: ReadonlyArray<string>,
  draft: BulkProgressDraft,
  stageSelections: ReadonlyArray<StageSelection> = [],
): BulkProgressInput {
  if (!draft.status) {
    throw new Error("Chọn trạng thái thi công trước khi gửi.");
  }
  const quantity = draft.quantity.trim() ? Number(draft.quantity) : null;
  if (quantity !== null && (!Number.isFinite(quantity) || quantity < 0)) {
    throw new Error("Khối lượng phải là số không âm.");
  }
  const selectedSet = new Set(selectedIds);
  return {
    stage_definition_id: draft.stage_definition_id.trim(),
    component_ids: [...selectedIds],
    stage_selections: stageSelections.filter((item) =>
      selectedSet.has(item.component_id),
    ),
    event_date: draft.event_date,
    status: draft.status,
    quantity,
    unit: draft.unit.trim() || null,
    note: draft.note.trim() || null,
    // Evidence is added from confirmed photos only; the UI does not invent it.
    evidence_refs: [],
  };
}

export function newProgressIdempotencyKey(
  random: string = typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`,
): string {
  return `progress:${random}`.slice(0, 120);
}

/** The server revalidates the exact selection; the UI never widens it. */
export function canCommitBulkPreview(preview: ProgressPreview | null): boolean {
  return Boolean(
    preview &&
      preview.can_commit &&
      preview.components.length > 0 &&
      preview.ambiguous_stage_component_ids.length === 0 &&
      preview.invalid_stage_component_ids.length === 0,
  );
}

/** Current Asia/Ho_Chi_Minh date as YYYY-MM-DD. */
export function todayISO(now: Date = new Date()): string {
  const shifted = new Date(now.getTime() + 7 * 60 * 60 * 1000);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(
    shifted.getUTCDate(),
  )}`;
}
