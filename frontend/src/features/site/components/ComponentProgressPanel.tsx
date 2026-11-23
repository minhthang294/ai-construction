import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ApiError,
  getDesignQuantities,
  listComponentProgress,
  listStageDefinitions,
  previewProgressBulk,
  saveProgressBulk,
} from "../lib/api";
import {
  EMPTY_BULK_PROGRESS,
  EMPTY_PROGRESS_FILTERS,
  acceptanceStatusLabel,
  ambiguousStageRows,
  buildBulkProgressPayload,
  buildDesignQuantityEntries,
  bulkProgressError,
  canCommitBulkPreview,
  constructionStatusLabel,
  filterProgressRows,
  groupDesignQuantityEntries,
  newProgressIdempotencyKey,
  scopeLabel,
  selectedProgressRows,
  selectedStageForRow,
  selectionsForSelected,
  sortStagesByPosition,
  stageDefinitionLabel,
  stageOptionsFor,
  todayISO,
  type BulkProgressDraft,
  type DesignQuantityGroup,
  type DesignQuantityMap,
  type ProgressFilters,
  type ProgressPreview,
  type ProgressRow,
  type StageDefinition,
} from "../lib/componentProgress";
import { formatISODate } from "../lib/datetime";
import BatchZoneBadge from "./BatchZoneBadge";
import ProgressHistoryPanel from "./ProgressHistoryPanel";
import QuickCodeEntry from "./QuickCodeEntry";

type Props = {
  projectId: string;
  batchId?: string | null;
  primaryZone?: string | null;
};

const PAGE_SIZE = 20;

const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-600 focus-visible:ring-offset-2";

const FIELD =
  "mt-1 min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300 sm:text-sm";

const PRIMARY_BUTTON =
  "min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-semibold text-white active:bg-slate-900 disabled:bg-slate-300";

const SECONDARY_BUTTON =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 active:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Không xác định được lỗi.";
}

const STATUS_STYLES: Record<string, string> = {
  NOT_STARTED: "app-status app-status--not-started",
  IN_PROGRESS: "app-status app-status--in-progress",
  COMPLETED: "app-status app-status--completed",
  BLOCKED: "app-status app-status--blocked",
};

function StatusChip({ status }: { status: string }) {
  return (
    <span className={STATUS_STYLES[status] ?? "app-status app-status--not-started"}>
      {constructionStatusLabel(status)}
    </span>
  );
}

function AcceptanceChip({ status }: { status: string }) {
  const tone =
    status === "APPROVED" || status === "CONFIRMED"
      ? "app-acceptance-badge app-acceptance-badge--confirmed"
      : status === "REJECTED"
        ? "app-acceptance-badge app-acceptance-badge--rejected"
        : status === "PENDING" || status === "CONDITIONAL"
          ? "app-acceptance-badge app-acceptance-badge--pending"
          : "app-acceptance-badge app-acceptance-badge--neutral";
  return (
    <span className={tone}>
      {acceptanceStatusLabel(status)}
    </span>
  );
}

function DesignQuantityList({ groups, showWork, showCodes }: {
  groups: DesignQuantityGroup[];
  showWork?: boolean;
  showCodes?: boolean;
}) {
  return (
    <ul className="divide-y divide-slate-200">
      {groups.flatMap(({ items }) => items).map((item) => (
        <li key={item.key} className="space-y-1 py-2">
          {showWork ? <p className="break-words text-sm text-slate-800">{item.stageNames.join(" · ")}</p> : null}
          <p className="break-words text-sm font-semibold text-slate-900">{item.quantityLabel}</p>
          {item.scope !== "COMPONENT" ? (
            <p className="break-words text-xs font-medium text-slate-800">
              {item.scope === "SHARED" ? "Dùng chung" : "Tổng theo nhóm"} · {item.scopeLabel}
            </p>
          ) : null}
          {showCodes ? <p className="break-words text-xs text-slate-700">{item.componentCodes.join(", ")}</p> : null}
          {item.drawing || item.page ? (
            <p className="text-xs text-slate-700">{[item.drawing, item.page ? `PDF trang ${item.page}` : null].filter(Boolean).join(" · ")}</p>
          ) : null}
          {item.note ? <p className="break-words text-xs text-slate-700">{item.note}</p> : null}
        </li>
      ))}
    </ul>
  );
}

type ProgressCardProps = {
  row: ProgressRow;
  projectId: string;
  primaryZone?: string | null;
  onChanged: () => void;
  selectionMode: boolean;
  selected: boolean;
  onToggle: () => void;
  onOpen: () => void;
};

function ProgressCard({
  row,
  projectId,
  primaryZone,
  onChanged,
  selectionMode,
  selected,
  onToggle,
  onOpen,
}: ProgressCardProps) {
  const event = row.construction_event;
  return (
    <article
      className={`min-w-0 rounded-xl border bg-white p-3 shadow-sm ${
        selected ? "border-slate-500 ring-1 ring-slate-400" : "border-slate-200"
      }`}
    >
      {selectionMode ? (
        <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-1 text-sm font-medium text-slate-800">
          <input
            type="checkbox"
            className="h-5 w-5 shrink-0 accent-slate-700"
            checked={selected}
            onChange={onToggle}
            aria-label={`Chọn ${row.canonical_code}`}
          />
          <span className="min-w-0 break-words">
            {selected ? "Đã chọn" : "Chọn cấu kiện"}
          </span>
        </label>
      ) : null}

      <div className="mt-1 flex min-w-0 flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="break-words font-mono text-base font-semibold text-slate-900">
            {row.canonical_code}
          </p>
          {row.raw_code !== row.canonical_code ? (
            <p className="break-words font-mono text-xs text-slate-600">
              Mã gốc: {row.raw_code}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-1">
          {row.scopes.includes("ADDITIONAL_SCOPE") ? (
            <span className="rounded-full border border-purple-200 bg-purple-50 px-2 py-0.5 text-xs text-purple-900">
              Phát sinh
            </span>
          ) : null}
          {row.verification !== "VERIFIED" ? (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-900">
              Chờ duyệt
            </span>
          ) : null}
        </div>
      </div>

      <p className="mt-1 break-words text-sm text-slate-600">
        {row.zone} · PĐ {row.segment_number} ·{" "}
        {row.type === "pile" ? "Cọc" : "Dầm"}
        {row.design_group ? ` · ${row.design_group}` : ""}
      </p>
      <div className="mt-1">
        <BatchZoneBadge
          zone={row.zone}
          segmentNumber={row.segment_number}
          primaryZone={primaryZone}
        />
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
        <div className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 p-2">
          <p className="font-medium text-slate-600">Thi công</p>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <StatusChip status={row.construction_status} />
            {event ? (
              <span className="break-words text-slate-600">
                {event.stage_name || event.stage_code || "—"} ·{" "}
                {formatISODate(event.event_date)}
              </span>
            ) : null}
          </div>
        </div>
        <div className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 p-2">
          <p className="font-medium text-slate-600">Nghiệm thu</p>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <AcceptanceChip status={row.acceptance_status} />
          </div>
        </div>
      </div>

      {row.stages.length ? (
        <details className="mt-2 rounded-lg border border-slate-200">
          <summary
            className={`flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 px-2 text-sm font-medium text-slate-700 [&::-webkit-details-marker]:hidden ${FOCUS_RING}`}
          >
            <span>Bước thi công ({row.stages.length})</span>
            <span aria-hidden="true" className="text-slate-500">
              ⌄
            </span>
          </summary>
          <ul className="space-y-1 border-t border-slate-200 p-2 text-xs text-slate-600">
            {sortStagesByPosition(row.stages).map((stage) => {
              const source = row.stages.find((item) => item.id === stage.inferred_from_stage_id);
              return (
                <li
                  key={stage.id}
                  className="flex min-w-0 flex-wrap items-center gap-1 break-words"
                >
                  <span className="min-w-0 break-words">{stage.name}</span>
                  {stage.scope_kind ? <span>· {scopeLabel(stage.scope_kind)}</span> : null}
                  <StatusChip status={stage.status} />
                  {stage.inference_conflict ? (
                    <span className="text-amber-800">Cần đối chiếu với bước sau</span>
                  ) : stage.inferred_from_stage_id ? (
                    <span className="text-slate-700">
                      Suy ra từ bước sau
                      {source ? ` · ${source.name}` : ""}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </details>
      ) : (
        <p className="mt-2 text-xs text-amber-800">Chưa gắn bước thi công.</p>
      )}

      {!selectionMode ? (
        <button
          type="button"
          className={`mt-2 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-sm font-semibold text-slate-800 active:bg-slate-100 ${FOCUS_RING}`}
          onClick={onOpen}
        >
          Ghi tiến độ
        </button>
      ) : null}
      <ProgressHistoryPanel
        projectId={projectId}
        componentId={row.id}
        onChanged={onChanged}
      />
    </article>
  );
}

export default function ComponentProgressPanel({ projectId, batchId, primaryZone }: Props) {
  const [rows, setRows] = useState<ProgressRow[]>([]);
  const [definitions, setDefinitions] = useState<StageDefinition[]>([]);
  const [definitionsError, setDefinitionsError] = useState(false);
  const [filters, setFilters] = useState<ProgressFilters>({
    ...EMPTY_PROGRESS_FILTERS,
  });
  const [draft, setDraft] = useState<BulkProgressDraft>({
    ...EMPTY_BULK_PROGRESS,
    event_date: todayISO(),
  });
  const [selected, setSelected] = useState<string[]>([]);
  const [stageSelections, setStageSelections] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<ProgressPreview | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState<"load" | "preview" | "save" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [mode, setMode] = useState<"browse" | "editor">("browse");
  const [selectionMode, setSelectionMode] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [designQuantities, setDesignQuantities] = useState<DesignQuantityMap>({});
  const [designStatus, setDesignStatus] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");

  const advancedId = useId();
  const browseHeadingRef = useRef<HTMLHeadingElement>(null);
  const editorHeadingRef = useRef<HTMLHeadingElement>(null);
  const previewHeadingRef = useRef<HTMLHeadingElement>(null);
  const previousMode = useRef(mode);

  const load = useCallback(async () => {
    setBusy("load");
    setError(null);
    try {
      setRows(await listComponentProgress(projectId, undefined, batchId));
    } catch (err) {
      setRows([]);
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }, [projectId, batchId]);

  const loadDefinitions = useCallback(async () => {
    setDefinitionsError(false);
    try {
      setDefinitions(await listStageDefinitions(projectId));
    } catch {
      // Rows still read; the editor can derive stages attached to each row.
      setDefinitions([]);
      setDefinitionsError(true);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
    void loadDefinitions();
  }, [load, loadDefinitions]);

  useEffect(() => {
    if (previousMode.current === mode) return;
    previousMode.current = mode;
    if (mode === "editor") editorHeadingRef.current?.focus();
    else browseHeadingRef.current?.focus();
  }, [mode]);

  useEffect(() => {
    if (preview) previewHeadingRef.current?.focus();
  }, [preview]);

  useEffect(() => {
    if (mode !== "editor" || selected.length === 0) return;
    const request = new AbortController();
    getDesignQuantities(projectId, selected, request.signal).then(
      (data) => {
        if (request.signal.aborted) return;
        setDesignQuantities(data);
        setDesignStatus("ready");
      },
      () => {
        if (!request.signal.aborted) setDesignStatus("error");
      },
    );
    return () => request.abort();
  }, [mode, projectId, selected]);

  const filtered = useMemo(
    () => filterProgressRows(rows, filters),
    [rows, filters],
  );
  const selectedRows = useMemo(
    () => selectedProgressRows(rows, selected),
    [rows, selected],
  );
  const selectedQuantityGroups = useMemo(() => {
    if (!draft.stage_definition_id) return [];
    const stageIds = new Set(selectedRows.map((row) =>
      selectedStageForRow(row, draft.stage_definition_id, stageSelections[row.id])?.id,
    ));
    return groupDesignQuantityEntries(
      buildDesignQuantityEntries(selectedRows, designQuantities, draft.stage_definition_id)
        .filter((entry) => stageIds.has(entry.stageId)),
    );
  }, [draft.stage_definition_id, designQuantities, selectedRows, stageSelections]);
  const allQuantityGroups = useMemo(
    () => selectedRows.length === 1
      ? groupDesignQuantityEntries(buildDesignQuantityEntries(selectedRows, designQuantities))
      : [],
    [selectedRows, designQuantities],
  );
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const quickCodeRows = useMemo(
    () =>
      rows.filter(
        (row) =>
          (!filters.zone || row.zone === filters.zone) &&
          (!filters.segment ||
            String(row.segment_number) === filters.segment),
      ),
    [rows, filters.zone, filters.segment],
  );
  const ambiguousSelectedRows = useMemo(
    () => ambiguousStageRows(selectedRows, draft.stage_definition_id),
    [selectedRows, draft.stage_definition_id],
  );
  const missingStageChoices = useMemo(
    () =>
      ambiguousSelectedRows.filter((row) => !stageSelections[row.id]).length,
    [ambiguousSelectedRows, stageSelections],
  );
  const selectedStageSelections = useMemo(
    () => selectionsForSelected(selected, stageSelections),
    [selected, stageSelections],
  );
  const zones = useMemo(
    () => Array.from(new Set(rows.map((row) => row.zone))),
    [rows],
  );
  const segmentOptions = useMemo(() => {
    const scopedRows = filters.zone
      ? rows.filter((row) => row.zone === filters.zone)
      : rows;
    return Array.from(
      new Map(
        scopedRows.map((row) => [
          String(row.segment_number),
          row.segment_number,
        ]),
      ).entries(),
    ).sort((left, right) => left[1] - right[1]);
  }, [rows, filters.zone]);

  const editorDefinitions = useMemo(() => {
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
  }, [definitions, selectedRows]);

  const activeFilterChips = useMemo(() => {
    const chips: string[] = [];
    if (filters.type) chips.push(filters.type === "pile" ? "Cọc" : "Dầm");
    if (filters.stage_definition_id) {
      const definition = definitions.find(
        (item) => item.id === filters.stage_definition_id,
      );
      chips.push(definition ? definition.name : "Bước thi công");
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
  }, [filters, definitions]);

  const advancedFilterCount = [
    filters.type,
    filters.stage_definition_id,
    filters.construction_status,
    filters.acceptance_status,
  ].filter(Boolean).length;
  const hasFilters = Boolean(
    filters.query.trim() || filters.zone || filters.segment || advancedFilterCount,
  );
  const visibleRows = filtered.slice(0, visibleCount);
  const remaining = Math.max(0, filtered.length - visibleRows.length);
  const filterSignature = JSON.stringify(filters);

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
    setSelected([]);
    setStageSelections({});
    setPreview(null);
    setConfirmed(false);
    setIdempotencyKey(null);
  }, [filterSignature]);

  function invalidatePreview() {
    setPreview(null);
    setConfirmed(false);
    setIdempotencyKey(null);
  }

  function updateFilter(patch: Partial<ProgressFilters>) {
    setFilters((current) => {
      const next = { ...current, ...patch };
      if ("zone" in patch && current.segment) {
        const stillAvailable = rows.some(
          (row) =>
            row.zone === next.zone &&
            String(row.segment_number) === current.segment,
        );
        if (next.zone && !stillAvailable) next.segment = "";
      }
      return next;
    });
  }

  function clearFilters() {
    setFilters({ ...EMPTY_PROGRESS_FILTERS });
  }

  function updateDraft(patch: Partial<BulkProgressDraft>) {
    setDraft((current) => ({ ...current, ...patch }));
    if ("stage_definition_id" in patch) setStageSelections({});
    invalidatePreview();
  }

  function updateStageSelection(componentId: string, stageId: string) {
    setStageSelections((current) => {
      const next = { ...current };
      if (stageId) next[componentId] = stageId;
      else delete next[componentId];
      return next;
    });
    invalidatePreview();
  }

  function toggleSelected(id: string) {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );
    invalidatePreview();
  }

  function clearSelection() {
    setSelected([]);
    setStageSelections({});
    invalidatePreview();
  }

  function toggleSelectionMode() {
    if (selectionMode) {
      setSelectionMode(false);
      clearSelection();
    } else {
      setSelectionMode(true);
      setSelected([]);
      invalidatePreview();
    }
  }

  function openEditor(ids: string[]) {
    if (!ids.length || busy) return;
    setDesignQuantities({});
    setDesignStatus("loading");
    setSelected(ids);
    setDraft({ ...EMPTY_BULK_PROGRESS, event_date: todayISO() });
    setStageSelections({});
    invalidatePreview();
    setError(null);
    setMessage(null);
    setSelectionMode(false);
    setMode("editor");
  }

  function closeEditor() {
    if (busy) return;
    setMode("browse");
    setSelected([]);
    setStageSelections({});
    setDraft({ ...EMPTY_BULK_PROGRESS, event_date: todayISO() });
    invalidatePreview();
    setError(null);
  }

  async function handlePreview() {
    const validation = bulkProgressError(
      draft,
      selected.length,
      missingStageChoices,
    );
    if (validation || busy) {
      setError(validation);
      return;
    }
    setBusy("preview");
    setError(null);
    setMessage(null);
    try {
      const data = await previewProgressBulk(
        projectId,
        buildBulkProgressPayload(selected, draft, selectedStageSelections),
      );
      setPreview(data);
      setConfirmed(false);
      setIdempotencyKey(newProgressIdempotencyKey());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleSave() {
    if (
      !preview ||
      !confirmed ||
      !canCommitBulkPreview(preview) ||
      !idempotencyKey ||
      busy
    ) {
      return;
    }
    setBusy("save");
    setError(null);
    try {
      const result = await saveProgressBulk(projectId, {
        ...buildBulkProgressPayload(selected, draft, selectedStageSelections),
        reviewed: true,
        idempotency_key: idempotencyKey,
      });
      setMessage(`Đã ghi ${result.created} sự kiện tiến độ.`);
      setSelected([]);
      setStageSelections({});
      setPreview(null);
      setConfirmed(false);
      setIdempotencyKey(null);
      setDraft({ ...EMPTY_BULK_PROGRESS, event_date: todayISO() });
      setSelectionMode(false);
      setMode("browse");
      await load();
    } catch (err) {
      // Keep the preview and key so an identical retry stays idempotent.
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className={`mx-auto w-full max-w-3xl space-y-3 ${selectionMode && selected.length ? "pb-24 lg:pb-0" : ""}`}>
      {error ? (
        <p
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          {error}
        </p>
      ) : null}
      {message ? (
        <p
          role="status"
          className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900"
        >
          {message}
        </p>
      ) : null}

      {mode === "browse" ? (
        <>
          <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <h4
                  ref={browseHeadingRef}
                  tabIndex={-1}
                  className="text-base font-semibold text-slate-900 focus:outline-none sm:text-lg"
                >
                  Tiến độ cấu kiện
                </h4>
                <p className="mt-1 text-xs text-slate-600">
                  {busy === "load" ? "Đang tải…" : `${filtered.length} cấu kiện`}
                </p>
              </div>
              <button
                type="button"
                aria-pressed={selectionMode}
                className={`${SECONDARY_BUTTON} shrink-0 ${FOCUS_RING}`}
                onClick={toggleSelectionMode}
              >
                {selectionMode ? "Xong" : "Chọn nhiều"}
              </button>
            </div>

            <label className="mt-3 block text-xs font-medium text-slate-700">
              Tìm mã cấu kiện
              <input
                type="search"
                inputMode="search"
                className={FIELD}
                value={filters.query}
                placeholder="Ví dụ F-66-67"
                aria-label="Tìm mã cấu kiện, nhóm hoặc bước"
                onChange={(event) => updateFilter({ query: event.target.value })}
              />
            </label>

            <div className="mt-2 grid grid-cols-2 gap-2">
              <label className="min-w-0 text-xs font-medium text-slate-700">
                Khu vực
                <select
                  className={FIELD}
                  value={filters.zone}
                  onChange={(event) => updateFilter({ zone: event.target.value })}
                >
                  <option value="">Tất cả khu</option>
                  {zones.map((zone) => (
                    <option key={zone} value={zone}>
                      {zone}
                    </option>
                  ))}
                </select>
              </label>
              <label className="min-w-0 text-xs font-medium text-slate-700">
                Phân đoạn
                <select
                  className={FIELD}
                  value={filters.segment}
                  onChange={(event) =>
                    updateFilter({ segment: event.target.value })
                  }
                >
                  <option value="">Tất cả phân đoạn</option>
                  {segmentOptions.map(([value, number]) => (
                    <option key={value} value={value}>
                      PĐ {number}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                aria-expanded={showAdvanced}
                aria-controls={advancedId}
                className={`${SECONDARY_BUTTON} ${FOCUS_RING}`}
                onClick={() => setShowAdvanced((current) => !current)}
              >
                Bộ lọc nâng cao
                {advancedFilterCount ? ` (${advancedFilterCount})` : ""}
              </button>
              {hasFilters ? (
                <button
                  type="button"
                  className={`${SECONDARY_BUTTON} ${FOCUS_RING}`}
                  onClick={clearFilters}
                >
                  Xóa lọc
                </button>
              ) : null}
            </div>

            {activeFilterChips.length ? (
              <div
                className="mt-2 flex flex-wrap gap-1"
                aria-label="Bộ lọc đang áp dụng"
              >
                {activeFilterChips.map((chip, index) => (
                  <span
                    key={`${chip}-${index}`}
                    className="max-w-full break-words rounded-full border border-slate-300 bg-slate-50 px-2 py-1 text-xs text-slate-700"
                  >
                    {chip}
                  </span>
                ))}
              </div>
            ) : null}

            {showAdvanced ? (
              <div
                id={advancedId}
                className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2"
              >
                <label className="min-w-0 text-xs font-medium text-slate-700">
                  Loại
                  <select
                    className={FIELD}
                    value={filters.type}
                    onChange={(event) =>
                      updateFilter({ type: event.target.value })
                    }
                  >
                    <option value="">Tất cả loại</option>
                    <option value="pile">Cọc</option>
                    <option value="beam">Dầm</option>
                  </select>
                </label>
                <label className="min-w-0 text-xs font-medium text-slate-700">
                  Bước thi công
                  <select
                    className={FIELD}
                    value={filters.stage_definition_id}
                    onChange={(event) =>
                      updateFilter({
                        stage_definition_id: event.target.value,
                      })
                    }
                  >
                    <option value="">Tất cả bước</option>
                    {definitions.map((definition) => (
                      <option key={definition.id} value={definition.id}>
                        {stageDefinitionLabel(definition)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="min-w-0 text-xs font-medium text-slate-700">
                  Thi công
                  <select
                    className={FIELD}
                    value={filters.construction_status}
                    onChange={(event) =>
                      updateFilter({
                        construction_status: event.target.value,
                      })
                    }
                  >
                    <option value="">Tất cả trạng thái</option>
                    <option value="NOT_STARTED">Chưa bắt đầu</option>
                    <option value="IN_PROGRESS">Đang thi công</option>
                    <option value="COMPLETED">Hoàn thành</option>
                    <option value="BLOCKED">Tạm dừng</option>
                  </select>
                </label>
                <label className="min-w-0 text-xs font-medium text-slate-700">
                  Nghiệm thu
                  <select
                    className={FIELD}
                    value={filters.acceptance_status}
                    onChange={(event) =>
                      updateFilter({
                        acceptance_status: event.target.value,
                      })
                    }
                  >
                    <option value="">Tất cả trạng thái</option>
                    <option value="NOT_LINKED">Chưa liên kết</option>
                    <option value="PENDING">Đang chờ</option>
                    <option value="APPROVED">Đã xác nhận</option>
                    <option value="CONDITIONAL">Có điều kiện</option>
                    <option value="REJECTED">Không đạt</option>
                    <option value="CONFIRMED">Đã xác nhận (khác)</option>
                  </select>
                </label>
                <button
                  type="button"
                  className={`${SECONDARY_BUTTON} justify-self-start ${FOCUS_RING}`}
                  disabled={busy === "load"}
                  onClick={() => void load()}
                >
                  Tải lại danh sách
                </button>
              </div>
            ) : null}

            {error && !showAdvanced ? (
              <button
                type="button"
                className={`${SECONDARY_BUTTON} mt-2 ${FOCUS_RING}`}
                disabled={busy === "load"}
                onClick={() => void load()}
              >
                Tải lại danh sách
              </button>
            ) : null}

            {definitionsError ? (
              <p className="mt-2 text-xs text-amber-800">
                Không tải được danh mục bước thi công.
              </p>
            ) : null}
          </div>

          {selectionMode ? (
            <>
              <p className="text-sm text-slate-700">
                Chọn từng cấu kiện. Đổi bộ lọc sẽ xóa lựa chọn.
              </p>
              <QuickCodeEntry
                rows={quickCodeRows}
                selectedIds={selected}
                disabled={busy !== null}
                onConfirm={(ids) => {
                  setSelected((current) =>
                    Array.from(new Set([...current, ...ids])),
                  );
                  invalidatePreview();
                }}
              />
              <div
                className={`flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-300 bg-white p-2 shadow-sm ${selected.length ? "fixed inset-x-3 bottom-[calc(3.75rem+max(0.5rem,env(safe-area-inset-bottom)))] z-20 mx-auto max-w-3xl shadow-md lg:static" : ""}`}
              >
                <p aria-live="polite" className="text-xs font-semibold text-slate-900">
                  Đã chọn {selected.length}
                </p>
                <div className="flex min-w-0 flex-wrap gap-2">
                  <button
                    type="button"
                    className={`${SECONDARY_BUTTON} flex-1 sm:flex-none ${FOCUS_RING}`}
                    disabled={selected.length === 0}
                    onClick={clearSelection}
                  >
                    Bỏ chọn
                  </button>
                  <button
                    type="button"
                    className={`${PRIMARY_BUTTON} flex-1 sm:flex-none ${FOCUS_RING}`}
                    disabled={selected.length === 0 || busy !== null}
                    onClick={() => openEditor(selected)}
                  >
                    Ghi tiến độ
                  </button>
                </div>
              </div>
            </>
          ) : null}

          <div className="space-y-2">
            {busy === "load" && rows.length === 0 ? (
              <p className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-600">
                Đang tải cấu kiện…
              </p>
            ) : null}
            {!busy && filtered.length === 0 ? (
              <p className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-600">
                {rows.length === 0
                  ? "Chưa có cấu kiện trong công trình."
                  : "Không có cấu kiện khớp bộ lọc."}
              </p>
            ) : null}
            {visibleRows.map((row) => (
              <ProgressCard
                key={row.id}
                row={row}
                projectId={projectId}
                primaryZone={primaryZone}
                onChanged={() => void load()}
                selectionMode={selectionMode}
                selected={selectedSet.has(row.id)}
                onToggle={() => toggleSelected(row.id)}
                onOpen={() => openEditor([row.id])}
              />
            ))}
            {remaining > 0 ? (
              <button
                type="button"
                className={`${SECONDARY_BUTTON} w-full ${FOCUS_RING}`}
                onClick={() =>
                  setVisibleCount((current) => current + PAGE_SIZE)
                }
              >
                Xem thêm {Math.min(PAGE_SIZE, remaining)} cấu kiện
              </button>
            ) : null}
          </div>
        </>
      ) : (
        <div className="space-y-3">
          <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex items-start gap-2">
              <button
                type="button"
                aria-label="Quay lại danh sách"
                className={`min-h-11 min-w-11 shrink-0 rounded-lg border border-slate-300 text-lg font-semibold text-slate-800 active:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400 ${FOCUS_RING}`}
                disabled={busy !== null}
                onClick={closeEditor}
              >
                ←
              </button>
              <div className="min-w-0">
                <h4
                  ref={editorHeadingRef}
                  tabIndex={-1}
                  className="text-lg font-semibold text-slate-900 focus:outline-none"
                >
                  Ghi tiến độ
                </h4>
                <p className="mt-1 text-xs text-slate-600">
                  {selectedRows.length} cấu kiện · một bước thi công
                </p>
              </div>
            </div>

            <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-2">
              <p className="text-xs font-medium text-slate-700">
                Cấu kiện đã chọn
              </p>
              <p className="mt-1 max-h-32 overflow-auto break-words font-mono text-sm text-slate-900">
                {selectedRows.map((row) => row.canonical_code).join(", ")}
              </p>
            </div>
          </div>

          {!preview ? (
          <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <label className="block text-xs font-medium text-slate-700">
              Bước thi công
              <select
                className={FIELD}
                value={draft.stage_definition_id}
                onChange={(event) =>
                  updateDraft({ stage_definition_id: event.target.value })
                }
              >
                <option value="">— Chọn bước —</option>
                {editorDefinitions.map((definition) => (
                  <option key={definition.id} value={definition.id}>
                    {definition.name}
                  </option>
                ))}
              </select>
            </label>
            {editorDefinitions.length === 0 ? (
              <p className="text-xs text-amber-800">
                Cấu kiện đã chọn chưa gắn bước thi công.
              </p>
            ) : null}

            <div className="min-w-0 rounded-lg bg-slate-50 px-3 py-2" aria-live="polite">
              <h5 className="text-sm font-semibold text-slate-900">Khối lượng thiết kế</h5>
              {designStatus === "loading" ? (
                <p className="mt-1 text-sm text-slate-700">Đang tải số liệu…</p>
              ) : designStatus === "error" ? (
                <p className="mt-1 text-sm text-slate-700">Chưa tải được số liệu thiết kế.</p>
              ) : selectedQuantityGroups.length ? (
                <DesignQuantityList groups={selectedQuantityGroups} showCodes={selectedRows.length > 1} />
              ) : (
                <p className="mt-1 text-sm text-slate-700">
                  {!draft.stage_definition_id && allQuantityGroups.length
                    ? "Chọn bước để xem khối lượng."
                    : draft.stage_definition_id && missingStageChoices
                      ? "Chọn phạm vi để xem khối lượng."
                      : "Chưa có khối lượng thiết kế cho lựa chọn này."}
                </p>
              )}
              {allQuantityGroups.length ? (
                <details className="mt-1 border-t border-slate-200">
                  <summary className={`min-h-11 py-3 text-sm font-medium text-slate-800 ${FOCUS_RING}`}>
                    Xem khối lượng các bước
                  </summary>
                  <DesignQuantityList groups={allQuantityGroups} showWork />
                </details>
              ) : null}
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="min-w-0 text-xs font-medium text-slate-700">
                Ngày ghi nhận
                <input
                  type="date"
                  className={FIELD}
                  value={draft.event_date}
                  onChange={(event) =>
                    updateDraft({ event_date: event.target.value })
                  }
                />
              </label>
              <label className="min-w-0 text-xs font-medium text-slate-700">
                Trạng thái
                <select
                  className={FIELD}
                  value={draft.status}
                  onChange={(event) =>
                    updateDraft({
                      status: event.target.value as BulkProgressDraft["status"],
                    })
                  }
                >
                  <option value="">— Chọn trạng thái —</option>
                  <option value="IN_PROGRESS">Đang thi công</option>
                  <option value="COMPLETED">Hoàn thành</option>
                  <option value="BLOCKED">Tạm dừng</option>
                </select>
              </label>
            </div>

            <details className="rounded-lg border border-slate-200">
              <summary
                className={`flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 px-2 text-sm font-medium text-slate-700 [&::-webkit-details-marker]:hidden ${FOCUS_RING}`}
              >
                <span>Thêm khối lượng, đơn vị, ghi chú</span>
                <span aria-hidden="true" className="text-slate-500">
                  ⌄
                </span>
              </summary>
              <div className="grid grid-cols-1 gap-2 border-t border-slate-200 p-2 sm:grid-cols-2">
                <label className="min-w-0 text-xs font-medium text-slate-700">
                  Khối lượng thực hiện
                  <input
                    inputMode="decimal"
                    className={FIELD}
                    value={draft.quantity}
                    placeholder="Để trống nếu chưa rõ"
                    onChange={(event) =>
                      updateDraft({ quantity: event.target.value })
                    }
                  />
                </label>
                <label className="min-w-0 text-xs font-medium text-slate-700">
                  Đơn vị
                  <input
                    maxLength={30}
                    className={FIELD}
                    value={draft.unit}
                    onChange={(event) => updateDraft({ unit: event.target.value })}
                  />
                </label>
                <label className="min-w-0 text-xs font-medium text-slate-700 sm:col-span-2">
                  Ghi chú
                  <textarea
                    maxLength={2000}
                    rows={2}
                    className={FIELD}
                    value={draft.note}
                    onChange={(event) => updateDraft({ note: event.target.value })}
                  />
                </label>
              </div>
            </details>

            {ambiguousSelectedRows.length ? (
              <div className="rounded-lg border border-slate-300 bg-slate-50 p-2 text-xs text-slate-800">
                <p className="font-medium">
                  Chọn phạm vi cho {ambiguousSelectedRows.length} cấu kiện
                </p>
                <p className="mt-1 text-slate-600">
                  Cùng một bước có ở nhiều phạm vi sửa chữa; máy chủ không tự
                  chọn.
                </p>
                <div className="mt-2 space-y-2">
                  {ambiguousSelectedRows.map((row) => (
                    <label
                      key={row.id}
                      className="grid gap-1 sm:grid-cols-[9rem_1fr] sm:items-center"
                    >
                      <span className="min-w-0 break-words font-mono font-semibold">
                        {row.canonical_code}
                      </span>
                      <select
                        className={FIELD}
                        value={stageSelections[row.id] ?? ""}
                        onChange={(event) =>
                          updateStageSelection(row.id, event.target.value)
                        }
                      >
                        <option value="">— Chọn phạm vi —</option>
                        {stageOptionsFor(row, draft.stage_definition_id).map(
                          (stage) => (
                            <option key={stage.id} value={stage.id}>
                              {scopeLabel(stage.scope_kind)} · {stage.name} ·{" "}
                              {constructionStatusLabel(stage.status)}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                  ))}
                </div>
              </div>
            ) : null}

            <button
              type="button"
              className={`${PRIMARY_BUTTON} w-full ${FOCUS_RING}`}
              disabled={busy !== null}
              onClick={() => void handlePreview()}
            >
              {busy === "preview" ? "Đang kiểm tra…" : "Xem lại trước khi lưu"}
            </button>
          </div>
          ) : null}

          {preview ? (
            <div className="space-y-3 rounded-xl border border-slate-300 bg-white p-3 shadow-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h4
                  ref={previewHeadingRef}
                  tabIndex={-1}
                  className="scroll-mt-32 text-base font-semibold text-slate-900"
                >
                  Xác nhận trước khi lưu
                </h4>
                <span className="text-xs text-slate-600">
                  {preview.ready_count}/{preview.count} sẵn sàng
                </span>
              </div>
              <div className="rounded-lg bg-slate-50 p-2 text-sm text-slate-700">
                <p className="break-words font-semibold">
                  {editorDefinitions.find((definition) => definition.id === draft.stage_definition_id)?.name}
                </p>
                <p className="mt-1">
                  {formatISODate(draft.event_date)} · {constructionStatusLabel(draft.status)}
                  {draft.quantity.trim() ? ` · ${draft.quantity} ${draft.unit}` : ""}
                </p>
              </div>

              {preview.warnings.length ? (
                <div
                  role="alert"
                  className="rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-900"
                >
                  <ul className="list-disc space-y-1 pl-5">
                    {preview.warnings.map((warning) => (
                      <li key={warning} className="break-words">
                        {warning}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="max-h-72 space-y-1 overflow-auto">
                {preview.components.map((row) => {
                  const chosen = row.stage_options.find(
                    (stage) => stage.id === row.stage_id,
                  );
                  return (
                    <div
                      key={row.id}
                      className="flex min-w-0 flex-wrap items-center justify-between gap-1 rounded-lg border border-slate-100 p-2 text-xs"
                    >
                      <span className="break-words font-mono font-semibold text-slate-900">
                        {row.canonical_code}
                      </span>
                      <span className="break-words text-slate-600">
                        {row.zone} · PĐ {row.segment_number}
                      </span>
                      <span
                        className={
                          row.stage_available
                            ? "break-words text-emerald-800"
                            : "break-words text-red-800"
                        }
                      >
                        {chosen
                          ? `Phạm vi: ${scopeLabel(chosen.scope_kind)}`
                          : row.stage_ambiguous
                            ? "Chọn phạm vi"
                            : row.stage_available
                              ? "Có bước thi công"
                              : "Thiếu bước"}
                      </span>
                    </div>
                  );
                })}
              </div>

              <label className="flex min-h-11 items-start gap-2 rounded-lg border border-slate-200 p-2 text-sm text-slate-800">
                <input
                  type="checkbox"
                  className="mt-0.5 h-5 w-5 shrink-0 accent-slate-700"
                  checked={confirmed}
                  disabled={!canCommitBulkPreview(preview) || busy !== null}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />
                <span>
                  Tôi đã kiểm tra đúng {preview.components.length} cấu kiện và
                  xác nhận ghi sự kiện ngày{" "}
                  {formatISODate(draft.event_date)}.
                </span>
              </label>

              <div className="flex flex-col gap-2 sm:flex-row">
                <button
                  type="button"
                  className={`${SECONDARY_BUTTON} ${FOCUS_RING}`}
                  disabled={busy !== null}
                  onClick={() => {
                    setError(null);
                    invalidatePreview();
                    editorHeadingRef.current?.focus();
                  }}
                >
                  Sửa thông tin
                </button>
                <button
                  type="button"
                  className={`${PRIMARY_BUTTON} flex-1 ${FOCUS_RING}`}
                  disabled={
                    !confirmed ||
                    !canCommitBulkPreview(preview) ||
                    busy !== null
                  }
                  onClick={() => void handleSave()}
                >
                  {busy === "save"
                    ? "Đang ghi tiến độ…"
                    : `Lưu ${preview.components.length} sự kiện đã duyệt`}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
