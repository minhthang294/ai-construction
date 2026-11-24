import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import ComponentProgressPanel from "./ComponentProgressPanel";
import DrawingMapPanel, { type PlacementTarget } from "./DrawingMapPanel";
import AdditionalComponentForm from "./AdditionalComponentForm";
import DailyProgressPanel from "./DailyProgressPanel";
import JournalPanel from "./JournalPanel";
import ConstructionBatchSelector from "./ConstructionBatchSelector";
import ConstructionBatchManager from "./ConstructionBatchManager";
import {
  useConstructionBatch,
  useConstructionBatches,
} from "../hooks/useConstructionBatch";
import {
  commitComponentImport,
  createComponent,
  listComponents,
  listSegments,
  previewComponentImport,
} from "../lib/api";
import {
  buildCommitPayload,
  buildManualComponentPayload,
  canCommitPreview,
  EMPTY_COMPONENT_FILTERS,
  EMPTY_MANUAL_COMPONENT,
  fileToBase64,
  filterPreviewComponents,
  manualComponentError,
  newIdempotencyKey,
  type ComponentFilters,
  type ComponentImportResult,
  type ComponentPreview,
  type ComponentSegment,
  type ComponentSummary,
  type ManualComponentDraft,
} from "../lib/componentImport";
import {
  PAGE_SIZE,
  errorMessage,
  type ComponentImportBusy,
  type ComponentView,
} from "../lib/componentCatalogImport";
import ComponentCatalogTabs from "./ComponentCatalogTabs";
import CatalogComponentList from "./CatalogComponentList";
import CatalogImportSection from "./CatalogImportSection";
import CatalogManualComponentForm from "./CatalogManualComponentForm";

type Props = {
  projectId: string;
  onOpenPaste?: () => void;
  /** Initial tab chosen by an app-level deep link. */
  initialView?: ComponentView;
  initialJournalDate?: string | null;
  /** Open this component's detail when set (e.g. from AI citations). */
  focusComponentId?: string | null;
  onFocusHandled?: () => void;
  /** Called after the journal deep link has been opened once. */
  onJournalOpened?: () => void;
  /** Called after any initial view deep link has been applied. */
  onViewOpened?: () => void;
};

export default function ComponentCatalogImport({
  projectId,
  onOpenPaste,
  initialView,
  initialJournalDate,
  focusComponentId,
  onFocusHandled,
  onJournalOpened,
  onViewOpened,
}: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ComponentPreview | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const [filters, setFilters] = useState<ComponentFilters>({
    ...EMPTY_COMPONENT_FILTERS,
  });
  const [visibleLimit, setVisibleLimit] = useState(PAGE_SIZE);
  const [workLinkLimit, setWorkLinkLimit] = useState(PAGE_SIZE);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState<ComponentImportBusy>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<ComponentImportResult | null>(null);

  const [catalog, setCatalog] = useState<ComponentSummary[]>([]);
  const [segments, setSegments] = useState<ComponentSegment[]>([]);
  const [search, setSearch] = useState("");
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogLimit, setCatalogLimit] = useState(PAGE_SIZE);

  const {
    batches,
    loading: batchesLoading,
    error: batchesError,
    reload: reloadBatches,
  } = useConstructionBatches(projectId);
  const { batchId, setBatchId } = useConstructionBatch(
    projectId,
    batches,
    batchesLoading,
  );
  const selectedBatch = batches.find((batch) => batch.id === batchId) ?? null;
  const primaryZone = selectedBatch?.primary_zone ?? null;
  const [mapPlacement, setMapPlacement] = useState<PlacementTarget | null>(null);
  const [mapRefreshKey, setMapRefreshKey] = useState(0);
  const handleAdditionalCreated = useCallback((component: ComponentSummary) => {
    setMapPlacement({
      componentId: component.id,
      code: component.canonical_code,
      type: component.type,
    });
    setMapRefreshKey((current) => current + 1);
  }, []);
  const handlePlacementDone = useCallback(() => {
    setMapPlacement(null);
    setMapRefreshKey((current) => current + 1);
  }, []);

  const [manual, setManual] = useState<ManualComponentDraft>({
    ...EMPTY_MANUAL_COMPONENT,
  });
  const [manualBusy, setManualBusy] = useState(false);
  const [manualError, setManualError] = useState<string | null>(null);
  const [manualMessage, setManualMessage] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement | null>(null);
  const tabId = useId();
  const [view, setView] = useState<ComponentView>(
    focusComponentId ? "progress" : initialView ?? "daily",
  );
  const [progressRequest, setProgressRequest] = useState<{ componentId: string; stageDefinitionId?: string | null } | null>(null);
  const requestDailyProgress = useCallback((componentId: string, stageDefinitionId?: string | null) => {
    setProgressRequest({ componentId, stageDefinitionId });
    setView("daily");
  }, []);
  const clearProgressRequest = useCallback(() => setProgressRequest(null), []);

  useEffect(() => {
    if (focusComponentId) setView("progress");
  }, [focusComponentId]);

  useEffect(() => {
    if (initialView === "journal") onJournalOpened?.();
    if (initialView) onViewOpened?.();
    // Deep link applies once per mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadCatalog = useCallback(
    async (query: string) => {
      setCatalogBusy(true);
      setCatalogLimit(PAGE_SIZE);
      try {
        setCatalog(await listComponents(projectId, query, batchId));
        setCatalogError(null);
      } catch (err) {
        setCatalogError(errorMessage(err));
      } finally {
        setCatalogBusy(false);
      }
    },
    [projectId, batchId],
  );

  const loadSegments = useCallback(async () => {
    try {
      setSegments(await listSegments(projectId));
    } catch {
      // Catalog filters are secondary; preview still works without them.
      setSegments([]);
    }
  }, [projectId]);

  useEffect(() => {
    if (view !== "catalog") return;
    void loadCatalog("");
    void loadSegments();
  }, [loadCatalog, loadSegments, view]);

  useEffect(() => {
    if (view !== "map") return;
    void loadSegments();
  }, [loadSegments, view]);

  const filtered = useMemo(
    () => filterPreviewComponents(preview?.components ?? [], filters),
    [preview, filters],
  );
  const visible = filtered.slice(0, visibleLimit);
  const canCommit = canCommitPreview(preview, Boolean(file));

  function updateFilter(patch: Partial<ComponentFilters>) {
    setFilters((current) => ({ ...current, ...patch }));
    setVisibleLimit(PAGE_SIZE);
  }

  function updateManual(patch: Partial<ManualComponentDraft>) {
    setManual((current) => ({ ...current, ...patch }));
  }

  function handleFileChange(next: File | null) {
    if (!next && inputRef.current) inputRef.current.value = "";
    setFile(next);
    setPreview(null);
    setIdempotencyKey(null);
    setFilters({ ...EMPTY_COMPONENT_FILTERS });
    setVisibleLimit(PAGE_SIZE);
    setWorkLinkLimit(PAGE_SIZE);
    setConfirmed(false);
    setError(null);
    setMessage(null);
    setResult(null);
  }

  async function handlePreview() {
    if (!file || busy) return;
    setBusy("preview");
    setError(null);
    setMessage(null);
    setResult(null);
    setConfirmed(false);
    try {
      const data = await previewComponentImport(projectId, file);
      setPreview(data);
      setWorkLinkLimit(PAGE_SIZE);
      setIdempotencyKey(newIdempotencyKey(data.source_sha256));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleCommit() {
    if (!preview || !file || !idempotencyKey || !confirmed || !canCommit || busy) {
      return;
    }
    setBusy("commit");
    setError(null);
    try {
      // Read the same file the preview came from; the server re-checks it.
      const sourceFileBase64 = await fileToBase64(file);
      const imported = await commitComponentImport(
        projectId,
        buildCommitPayload(preview, sourceFileBase64, idempotencyKey),
      );
      setResult(imported);
      setMessage(
        `Đã nhập ${imported.components} cấu kiện, ${imported.segments} phân đoạn, ${imported.work_links} liên kết công việc.`,
      );
      setPreview(null);
      setFile(null);
      setConfirmed(false);
      setIdempotencyKey(null);
      if (inputRef.current) inputRef.current.value = "";
      await loadCatalog(search);
      // A workbook import can create the segments used by the manual form.
      await loadSegments();
    } catch (err) {
      // Keep the preview and key so the user can retry the same idempotent batch.
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleCreateManual() {
    const validation = manualComponentError(manual);
    if (validation) {
      setManualError(validation);
      return;
    }
    setManualBusy(true);
    setManualError(null);
    setManualMessage(null);
    try {
      const created = await createComponent(
        projectId,
        buildManualComponentPayload(manual),
      );
      setManual((current) => ({
        ...current,
        type: "",
        scope: "",
        raw_code: "",
        canonical_code: "",
      }));
      const verification =
        created.verification === "NEEDS_REVIEW"
          ? "Chờ duyệt"
          : created.verification;
      setManualMessage(
        `Đã tạo cấu kiện ${created.canonical_code} · xác minh danh mục: ${verification}.`,
      );
      // Reload the full list so the new row is visible even when a search is active.
      setSearch("");
      await loadCatalog("");
    } catch (err) {
      setManualError(errorMessage(err));
    } finally {
      setManualBusy(false);
    }
  }

  return (
    <section className="space-y-4">
      <ConstructionBatchSelector
        batches={batches}
        value={batchId}
        onChange={setBatchId}
        loading={batchesLoading}
        error={batchesError}
        onManage={() =>
          document.getElementById("batch-manager")?.scrollIntoView({ behavior: "smooth", block: "start" })
        }
      />
      <ConstructionBatchManager
        projectId={projectId}
        batchId={batchId}
        batches={batches}
        onSelect={setBatchId}
        onChanged={() => void reloadBatches()}
      />
      <ComponentCatalogTabs view={view} tabId={tabId} onChange={setView} />

      <div
        id={`${tabId}-panel`}
        role="tabpanel"
        aria-labelledby={`${tabId}-${view}`}
        className="space-y-3"
      >
      {view === "daily" ? (
        <DailyProgressPanel
          projectId={projectId}
          batchId={batchId}
          primaryZone={primaryZone}
          initialComponentId={progressRequest?.componentId}
          initialStageDefinitionId={progressRequest?.stageDefinitionId}
          onInitialComponentHandled={clearProgressRequest}
          onOpenPaste={onOpenPaste}
        />
      ) : view === "progress" ? (
        <ComponentProgressPanel
          projectId={projectId}
          batchId={batchId}
          primaryZone={primaryZone}
          focusComponentId={focusComponentId}
          onFocusHandled={onFocusHandled}
        />
      ) : view === "journal" ? (
        <JournalPanel projectId={projectId} initialDate={initialJournalDate} />
      ) : view === "map" ? (
        <div className="space-y-3">
          <AdditionalComponentForm
            key={batchId ?? "no-batch"}
            projectId={projectId}
            batchId={batchId}
            segments={segments}
            primaryZone={primaryZone}
            onCreated={handleAdditionalCreated}
          />
          <DrawingMapPanel
            projectId={projectId}
            batchId={batchId}
            onRequestProgress={requestDailyProgress}
            placement={mapPlacement}
            onPlacementDone={handlePlacementDone}
            refreshKey={mapRefreshKey}
          />
        </div>
      ) : (
        <>
          <CatalogComponentList
            catalog={catalog}
            segments={segments}
            search={search}
            catalogBusy={catalogBusy}
            catalogError={catalogError}
            catalogLimit={catalogLimit}
            primaryZone={primaryZone}
            onSearchChange={setSearch}
            onSearch={() => void loadCatalog(search)}
            onLoadMore={() => setCatalogLimit((current) => current + PAGE_SIZE)}
          />

          <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-950">
            Chỉ nhập <strong>danh mục cấu kiện</strong>. Không tạo tiến độ thi
            công hoặc nghiệm thu; ngày trong workbook không phải sự kiện thực tế.
          </div>

          <CatalogImportSection
            file={file}
            preview={preview}
            busy={busy}
            error={error}
            message={message}
            result={result}
            inputRef={inputRef}
            filters={filters}
            visible={visible}
            filteredCount={filtered.length}
            canCommit={canCommit}
            confirmed={confirmed}
            workLinkLimit={workLinkLimit}
            onFileChange={handleFileChange}
            onPreview={() => void handlePreview()}
            onFilterChange={updateFilter}
            onConfirmedChange={setConfirmed}
            onLoadMoreVisible={() =>
              setVisibleLimit((current) => current + PAGE_SIZE)
            }
            onWorkLinkLimitChange={setWorkLinkLimit}
            onCommit={() => void handleCommit()}
          />

          <CatalogManualComponentForm
            manual={manual}
            segments={segments}
            manualBusy={manualBusy}
            manualError={manualError}
            manualMessage={manualMessage}
            onChange={updateManual}
            onSubmit={() => void handleCreateManual()}
          />
        </>
      )}
      </div>
    </section>
  );
}
