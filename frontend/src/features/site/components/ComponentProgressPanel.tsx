import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  getDesignQuantities,
  listComponentProgress,
  listStageDefinitions,
  previewProgressBulk,
  saveProgressBulk,
} from "../lib/api";
import {
  EMPTY_BULK_PROGRESS,
  EMPTY_PROGRESS_FILTERS,
  ambiguousStageRows,
  buildBulkProgressPayload,
  bulkProgressError,
  canCommitBulkPreview,
  filterProgressRows,
  newProgressIdempotencyKey,
  selectedProgressRows,
  selectionsForSelected,
  todayISO,
  type BulkProgressDraft,
  type DesignQuantityMap,
  type ProgressFilters,
  type ProgressPreview,
  type ProgressRow,
  type StageDefinition,
} from "../lib/componentProgress";
import {
  PROGRESS_PAGE_SIZE,
  allStageQuantityGroups,
  buildActiveFilterChips,
  countAdvancedFilters,
  editorDefinitionsFor,
  errorMessage,
  hasProgressFilters,
  quickCodeRowsFor,
  segmentOptionsFor,
  selectedStageQuantityGroups,
  type ProgressBusy,
} from "../lib/componentProgressPanel";
import ComponentProgressBanners from "./ComponentProgressBanners";
import ComponentProgressEditor from "./ComponentProgressEditor";
import ComponentProgressEditorHeader from "./ComponentProgressEditorHeader";
import ComponentProgressList from "./ComponentProgressList";
import ComponentProgressPreview from "./ComponentProgressPreview";
import ComponentProgressSelection from "./ComponentProgressSelection";
import ComponentProgressToolbar from "./ComponentProgressToolbar";

type Props = {
  projectId: string;
  batchId?: string | null;
  primaryZone?: string | null;
  /** Open this component's detail/editor when set (e.g. from AI citations). */
  focusComponentId?: string | null;
  onFocusHandled?: () => void;
};

export default function ComponentProgressPanel({
  projectId,
  batchId,
  primaryZone,
  focusComponentId,
  onFocusHandled,
}: Props) {
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
  const [busy, setBusy] = useState<ProgressBusy>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [mode, setMode] = useState<"browse" | "editor">("browse");
  const [selectionMode, setSelectionMode] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [visibleCount, setVisibleCount] = useState(PROGRESS_PAGE_SIZE);
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
    if (!focusComponentId || rows.length === 0) return;
    const row = rows.find((item) => item.id === focusComponentId);
    onFocusHandled?.();
    if (!row) return;
    setFilters({ ...EMPTY_PROGRESS_FILTERS });
    setVisibleCount(PROGRESS_PAGE_SIZE);
    setDesignQuantities({});
    setDesignStatus("loading");
    setSelected([row.id]);
    setDraft({ ...EMPTY_BULK_PROGRESS, event_date: todayISO() });
    setStageSelections({});
    setPreview(null);
    setConfirmed(false);
    setIdempotencyKey(null);
    setError(null);
    setMessage(null);
    setSelectionMode(false);
    setMode("editor");
  }, [focusComponentId, rows, onFocusHandled]);

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

  const filtered = useMemo(() => filterProgressRows(rows, filters), [rows, filters]);
  const selectedRows = useMemo(() => selectedProgressRows(rows, selected), [rows, selected]);
  const selectedQuantityGroups = useMemo(
    () => selectedStageQuantityGroups(selectedRows, designQuantities, draft.stage_definition_id, stageSelections),
    [draft.stage_definition_id, designQuantities, selectedRows, stageSelections],
  );
  const allQuantityGroups = useMemo(
    () => allStageQuantityGroups(selectedRows, designQuantities),
    [selectedRows, designQuantities],
  );
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const quickCodeRows = useMemo(() => quickCodeRowsFor(rows, filters), [rows, filters.zone, filters.segment]);
  const ambiguousSelectedRows = useMemo(
    () => ambiguousStageRows(selectedRows, draft.stage_definition_id),
    [selectedRows, draft.stage_definition_id],
  );
  const missingStageChoices = useMemo(
    () => ambiguousSelectedRows.filter((row) => !stageSelections[row.id]).length,
    [ambiguousSelectedRows, stageSelections],
  );
  const selectedStageSelections = useMemo(
    () => selectionsForSelected(selected, stageSelections),
    [selected, stageSelections],
  );
  const zones = useMemo(() => Array.from(new Set(rows.map((row) => row.zone))), [rows]);
  const segmentOptions = useMemo(() => segmentOptionsFor(rows, filters.zone), [rows, filters.zone]);
  const editorDefinitions = useMemo(() => editorDefinitionsFor(definitions, selectedRows), [definitions, selectedRows]);
  const activeFilterChips = useMemo(() => buildActiveFilterChips(filters, definitions), [filters, definitions]);
  const advancedFilterCount = countAdvancedFilters(filters);
  const hasFilters = hasProgressFilters(filters);
  const visibleRows = filtered.slice(0, visibleCount);
  const remaining = Math.max(0, filtered.length - visibleRows.length);
  const filterSignature = JSON.stringify(filters);

  useEffect(() => {
    setVisibleCount(PROGRESS_PAGE_SIZE);
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

  function handleQuickCodeConfirm(ids: string[]) {
    setSelected((current) => Array.from(new Set([...current, ...ids])));
    invalidatePreview();
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

  function handleEditFromPreview() {
    setError(null);
    invalidatePreview();
    editorHeadingRef.current?.focus();
  }

  return (
    <section className={`mx-auto w-full max-w-3xl space-y-3 ${selectionMode && selected.length ? "pb-24 lg:pb-0" : ""}`}>
      <ComponentProgressBanners error={error} message={message} />

      {mode === "browse" ? (
        <>
          <ComponentProgressToolbar
            filters={filters}
            updateFilter={updateFilter}
            clearFilters={clearFilters}
            zones={zones}
            segmentOptions={segmentOptions}
            definitions={definitions}
            activeFilterChips={activeFilterChips}
            advancedFilterCount={advancedFilterCount}
            hasFilters={hasFilters}
            filteredCount={filtered.length}
            busy={busy}
            error={error}
            definitionsError={definitionsError}
            selectionMode={selectionMode}
            onToggleSelectionMode={toggleSelectionMode}
            showAdvanced={showAdvanced}
            onToggleAdvanced={() => setShowAdvanced((current) => !current)}
            onLoad={() => void load()}
            headingRef={browseHeadingRef}
            advancedId={advancedId}
          />

          {selectionMode ? (
            <ComponentProgressSelection
              selected={selected}
              quickCodeRows={quickCodeRows}
              busy={busy}
              onQuickCodeConfirm={handleQuickCodeConfirm}
              onClearSelection={clearSelection}
              onOpenEditor={() => openEditor(selected)}
            />
          ) : null}

          <ComponentProgressList
            rows={rows}
            filteredCount={filtered.length}
            visibleRows={visibleRows}
            busy={busy}
            selectionMode={selectionMode}
            selectedIds={selectedSet}
            projectId={projectId}
            primaryZone={primaryZone}
            remaining={remaining}
            onLoadMore={() =>
              setVisibleCount((current) => current + PROGRESS_PAGE_SIZE)
            }
            onChanged={() => void load()}
            onToggle={toggleSelected}
            onOpen={(id) => openEditor([id])}
          />
        </>
      ) : (
        <div className="space-y-3">
          <ComponentProgressEditorHeader
            selectedRows={selectedRows}
            busy={busy}
            onClose={closeEditor}
            headingRef={editorHeadingRef}
          />

          {!preview ? (
            <ComponentProgressEditor
              selectedRows={selectedRows}
              draft={draft}
              updateDraft={updateDraft}
              editorDefinitions={editorDefinitions}
              designStatus={designStatus}
              selectedQuantityGroups={selectedQuantityGroups}
              allQuantityGroups={allQuantityGroups}
              missingStageChoices={missingStageChoices}
              ambiguousSelectedRows={ambiguousSelectedRows}
              stageSelections={stageSelections}
              updateStageSelection={updateStageSelection}
              busy={busy}
              onPreview={() => void handlePreview()}
            />
          ) : null}

          {preview ? (
            <ComponentProgressPreview
              preview={preview}
              editorDefinitions={editorDefinitions}
              draft={draft}
              confirmed={confirmed}
              onConfirmedChange={setConfirmed}
              busy={busy}
              headingRef={previewHeadingRef}
              onEdit={handleEditFromPreview}
              onSave={() => void handleSave()}
            />
          ) : null}
        </div>
      )}
    </section>
  );
}
