import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import ComponentProgressPanel from "./ComponentProgressPanel";
import DrawingMapPanel from "./DrawingMapPanel";
import DailyProgressPanel from "./DailyProgressPanel";
import JournalPanel from "./JournalPanel";
import ConstructionBatchSelector from "./ConstructionBatchSelector";
import ConstructionBatchManager from "./ConstructionBatchManager";
import BatchZoneBadge from "./BatchZoneBadge";
import {
  useConstructionBatch,
  useConstructionBatches,
} from "../hooks/useConstructionBatch";
import {
  ApiError,
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
  summarizePreview,
  type ComponentCandidate,
  type ComponentFilters,
  type ComponentImportResult,
  type ComponentPreview,
  type ComponentSegment,
  type ComponentSummary,
  type ManualComponentDraft,
} from "../lib/componentImport";

type Props = { projectId: string; onOpenPaste?: () => void };

const PAGE_SIZE = 100;
const COMPONENT_VIEWS = [
  { id: "daily", label: "Ghi theo ngày" },
  { id: "progress", label: "Theo cấu kiện" },
  { id: "catalog", label: "Danh mục" },
  { id: "journal", label: "Nhật ký" },
  { id: "map", label: "Mặt bằng" },
] as const;
const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-700 focus-visible:ring-offset-2";
const FIELD_CLASS = `min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-base text-slate-900 placeholder:text-slate-400 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-slate-500 ${FOCUS_RING}`;
const PRIMARY_BUTTON = `min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-semibold text-white active:bg-slate-900 disabled:cursor-not-allowed disabled:bg-gray-300 ${FOCUS_RING}`;
const SECONDARY_BUTTON = `min-h-11 rounded-lg border border-gray-300 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-gray-100 ${FOCUS_RING}`;
const DETAILS_SUMMARY = `flex min-h-11 cursor-pointer flex-wrap items-center justify-between gap-2 px-3 py-2 text-left ${FOCUS_RING}`;

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Không xác định được lỗi.";
}

function segmentLabel(segment: ComponentSegment): string {
  return `${segment.zone} · PĐ ${segment.number}`;
}

function CandidateCard({ component }: { component: ComponentCandidate }) {
  return (
    <article className="rounded-xl border border-gray-200 bg-white p-3 text-sm shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="break-all font-mono text-base font-semibold text-slate-900">
            {component.canonical_code}
          </p>
          {component.raw_code !== component.canonical_code ? (
            <p className="font-mono text-xs text-amber-700">
              Mã gốc: {component.raw_code}
            </p>
          ) : null}
        </div>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
          dòng {component.source_row}
        </span>
      </div>
      <dl className="mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-slate-600">Mã nguồn</dt>
          <dd className="break-all font-mono">{component.source_id}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Khu / phân đoạn</dt>
          <dd>
            {component.zone} · PĐ {component.segment}
          </dd>
        </div>
        <div>
          <dt className="text-slate-600">Loại</dt>
          <dd>{component.type === "pile" ? "Cọc" : "Dầm"}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Phạm vi</dt>
          <dd>{component.scope === "ADDITIONAL_SCOPE" ? "Phát sinh sửa chữa" : "Theo thiết kế"}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Nhóm thiết kế</dt>
          <dd>{component.design_group ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Bản vẽ</dt>
          <dd>{component.drawing || "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Nguồn</dt>
          <dd>{component.source || "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Xác minh danh mục</dt>
          <dd>Chờ duyệt</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-slate-600">Tên khác</dt>
          <dd className="break-all font-mono">
            {component.aliases.length ? component.aliases.join(", ") : "—"}
          </dd>
        </div>
      </dl>
    </article>
  );
}

export default function ComponentCatalogImport({ projectId, onOpenPaste }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ComponentPreview | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const [filters, setFilters] = useState<ComponentFilters>({
    ...EMPTY_COMPONENT_FILTERS,
  });
  const [visibleLimit, setVisibleLimit] = useState(PAGE_SIZE);
  const [workLinkLimit, setWorkLinkLimit] = useState(PAGE_SIZE);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState<"preview" | "commit" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<ComponentImportResult | null>(null);

  const [catalog, setCatalog] = useState<ComponentSummary[]>([]);
  const [segments, setSegments] = useState<ComponentSegment[]>([]);
  const [search, setSearch] = useState("");
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogLimit, setCatalogLimit] = useState(PAGE_SIZE);

  const { batchId, setBatchId } = useConstructionBatch(projectId);
  const {
    batches,
    loading: batchesLoading,
    error: batchesError,
    reload: reloadBatches,
  } = useConstructionBatches(projectId);
  const selectedBatch = batches.find((batch) => batch.id === batchId) ?? null;
  const primaryZone = selectedBatch?.primary_zone ?? null;

  const [manual, setManual] = useState<ManualComponentDraft>({
    ...EMPTY_MANUAL_COMPONENT,
  });
  const [manualBusy, setManualBusy] = useState(false);
  const [manualError, setManualError] = useState<string | null>(null);
  const [manualMessage, setManualMessage] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement | null>(null);
  const tabId = useId();
  const [view, setView] = useState<(typeof COMPONENT_VIEWS)[number]["id"]>(
    "daily",
  );
  const [progressRequest, setProgressRequest] = useState<{ componentId: string; stageDefinitionId?: string | null } | null>(null);
  const requestDailyProgress = useCallback((componentId: string, stageDefinitionId?: string | null) => {
    setProgressRequest({ componentId, stageDefinitionId });
    setView("daily");
  }, []);
  const clearProgressRequest = useCallback(() => setProgressRequest(null), []);

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

  const zones = useMemo(
    () => Array.from(new Set((preview?.components ?? []).map((item) => item.zone))),
    [preview],
  );
  const segmentNumbers = useMemo(
    () =>
      Array.from(
        new Set((preview?.segments ?? []).map((item) => String(item.number))),
      ).sort((left, right) => Number(left) - Number(right)),
    [preview],
  );
  const filtered = useMemo(
    () => filterPreviewComponents(preview?.components ?? [], filters),
    [preview, filters],
  );
  const visible = filtered.slice(0, visibleLimit);
  const visibleCatalog = catalog.slice(0, catalogLimit);
  const summary = preview ? summarizePreview(preview) : null;
  const canCommit = canCommitPreview(preview, Boolean(file));

  const segmentById = useMemo(
    () => new Map(segments.map((item) => [item.id, item])),
    [segments],
  );

  function updateFilter(patch: Partial<ComponentFilters>) {
    setFilters((current) => ({ ...current, ...patch }));
    setVisibleLimit(PAGE_SIZE);
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
      />
      <ConstructionBatchManager
        projectId={projectId}
        batchId={batchId}
        batches={batches}
        onSelect={setBatchId}
        onChanged={() => void reloadBatches()}
      />
      <div
        className="grid grid-cols-3 gap-1 rounded-xl border border-gray-200 bg-white p-1 shadow-sm sm:grid-cols-5"
        role="tablist"
        aria-label="Tiến độ, danh mục, nhật ký và mặt bằng cấu kiện"
        onKeyDown={(event) => {
          const current = COMPONENT_VIEWS.findIndex((item) => item.id === view);
          const last = COMPONENT_VIEWS.length - 1;
          const next = event.key === "Home" ? 0
            : event.key === "End" ? last
              : event.key === "ArrowRight" ? (current + 1) % COMPONENT_VIEWS.length
                : event.key === "ArrowLeft" ? (current + last) % COMPONENT_VIEWS.length
                  : -1;
          if (next < 0) return;
          event.preventDefault();
          setView(COMPONENT_VIEWS[next].id);
          event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
        }}
      >
        {COMPONENT_VIEWS.map(({ id, label }) => (
          <button
            key={id}
            id={`${tabId}-${id}`}
            type="button"
            role="tab"
            aria-selected={view === id}
            aria-controls={`${tabId}-panel`}
            tabIndex={view === id ? 0 : -1}
            className={`min-h-11 min-w-0 flex-1 rounded-lg px-2 sm:px-3 ${
              view === id ? "bg-slate-800 text-white shadow-sm" : "text-slate-700 hover:bg-slate-100"
            } ${FOCUS_RING}`}
            onClick={() => setView(id)}
          >
            <span className="text-sm font-semibold">{label}</span>
          </button>
        ))}
      </div>

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
        />
      ) : view === "journal" ? (
        <JournalPanel projectId={projectId} />
      ) : view === "map" ? (
        <DrawingMapPanel projectId={projectId} batchId={batchId} onRequestProgress={requestDailyProgress} />
      ) : (
        <>
          <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h3 className="text-base font-semibold text-slate-900">
                  Danh mục hiện có
                </h3>
                <p className="text-xs text-slate-600">
                  Tìm theo mã chuẩn hoặc tên khác đã nhập.
                </p>
              </div>
              <span className="text-xs font-medium text-slate-600">
                {catalog.length} dòng
              </span>
            </div>

            <form
              className="mt-3 flex flex-col gap-2 sm:flex-row"
              onSubmit={(event) => {
                event.preventDefault();
                void loadCatalog(search);
              }}
            >
              <input
                className={`${FIELD_CLASS} min-w-0 flex-1`}
                value={search}
                placeholder="Ví dụ I40-42"
                aria-label="Tìm cấu kiện theo mã hoặc tên khác"
                onChange={(event) => setSearch(event.target.value)}
              />
              <button
                type="submit"
                className={`${PRIMARY_BUTTON} sm:w-auto`}
                disabled={catalogBusy}
              >
                {catalogBusy ? "Đang tải…" : "Tìm"}
              </button>
            </form>

            {catalogError ? (
              <p
                role="alert"
                className="mt-2 rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-800"
              >
                {catalogError}
              </p>
            ) : null}

            <div className="mt-3 space-y-2">
              {visibleCatalog.map((component) => {
                const segment = segmentById.get(component.segment_id);
                return (
                  <div
                    key={component.id}
                    className="rounded-lg border border-gray-200 p-3 text-sm"
                  >
                    <p className="break-all font-mono text-base font-semibold text-slate-900">
                      {component.canonical_code}
                    </p>
                    {component.raw_code !== component.canonical_code ? (
                      <p className="font-mono text-xs text-amber-700">
                        Mã gốc: {component.raw_code}
                      </p>
                    ) : null}
                    <p className="mt-1 text-xs text-slate-600">
                      {segment ? segmentLabel(segment) : component.segment_id} ·{" "}
                      <span>{component.type === "pile" ? "Cọc" : "Dầm"}</span> ·{" "}
                      <span>
                        {component.verification === "VERIFIED"
                          ? "Đã duyệt danh mục"
                          : "Chờ duyệt"}
                      </span>
                    </p>
                    <div className="mt-1">
                      <BatchZoneBadge
                        zone={component.zone ?? segment?.zone ?? ""}
                        segmentNumber={component.segment_number ?? segment?.number ?? 0}
                        primaryZone={primaryZone}
                      />
                    </div>
                  </div>
                );
              })}
              {!catalogBusy && catalog.length === 0 && !catalogError ? (
                <p className="rounded-lg border border-gray-200 p-3 text-sm text-slate-600">
                  {search.trim()
                    ? "Không tìm thấy cấu kiện khớp mã hoặc alias."
                    : "Chưa có cấu kiện trong công trình."}
                </p>
              ) : null}
            </div>

            {catalogLimit < catalog.length ? (
              <div className="mt-3 space-y-2">
                <p className="text-xs text-slate-600">
                  Hiển thị {visibleCatalog.length}/{catalog.length} dòng.
                </p>
                <button
                  type="button"
                  className={`${SECONDARY_BUTTON} w-full`}
                  onClick={() => setCatalogLimit((current) => current + PAGE_SIZE)}
                >
                  Xem thêm{" "}
                  {Math.min(PAGE_SIZE, catalog.length - catalogLimit)} dòng
                </button>
              </div>
            ) : null}
          </div>

          <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-950">
            Chỉ nhập <strong>danh mục cấu kiện</strong>. Không tạo tiến độ thi
            công hoặc nghiệm thu; ngày trong workbook không phải sự kiện thực tế.
          </div>

          <details className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <summary className={DETAILS_SUMMARY}>
              <span className="text-base font-semibold text-slate-900">
                Nhập danh mục từ workbook
              </span>
              <span className="text-xs font-normal text-slate-600">
                XLSX · tối đa 10 MB
              </span>
            </summary>
            <div className="border-t border-gray-100 p-3">
              <p className="text-xs text-slate-600">
                Máy chủ đọc file và luôn tạo preview trước khi nhập. UI không tự
                sửa dữ liệu.
              </p>
              <input
                ref={inputRef}
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                disabled={busy !== null}
                aria-label="Chọn workbook danh mục cấu kiện"
                className={`${FIELD_CLASS} mt-3 file:mr-3 file:min-h-11 file:rounded-md file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white`}
                onChange={(event) =>
                  handleFileChange(event.target.files?.[0] ?? null)
                }
              />
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <button
                  type="button"
                  className={`min-h-11 flex-1 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white active:bg-blue-800 disabled:cursor-not-allowed disabled:bg-gray-300 ${FOCUS_RING}`}
                  disabled={!file || busy !== null}
                  onClick={() => void handlePreview()}
                >
                  {busy === "preview"
                    ? "Đang đọc workbook…"
                    : "Tạo bản xem trước"}
                </button>
                {preview ? (
                  <button
                    type="button"
                    className={`${SECONDARY_BUTTON} sm:w-auto`}
                    disabled={busy !== null}
                    onClick={() => handleFileChange(null)}
                  >
                    Hủy preview
                  </button>
                ) : null}
              </div>

              {error ? (
                <p
                  role="alert"
                  className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"
                >
                  {error}
                </p>
              ) : null}
              {message ? (
                <p
                  role="status"
                  className="mt-3 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800"
                >
                  {message}
                </p>
              ) : null}
              {result ? (
                <dl className="mt-3 grid grid-cols-3 gap-2 rounded-lg border border-green-200 bg-white p-3 text-center text-sm">
                  <div>
                    <dt className="text-xs text-slate-600">Cấu kiện</dt>
                    <dd className="text-lg font-semibold text-slate-900">
                      {result.components}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-600">Phân đoạn</dt>
                    <dd className="text-lg font-semibold text-slate-900">
                      {result.segments}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-600">Liên kết</dt>
                    <dd className="text-lg font-semibold text-slate-900">
                      {result.work_links}
                    </dd>
                  </div>
                </dl>
              ) : null}

              {preview && summary ? (
                <div className="mt-3 space-y-3 rounded-xl border border-gray-200 bg-slate-50 p-3">
                  <div>
                    <h4 className="text-base font-semibold text-slate-900">
                      Preview từ máy chủ
                    </h4>
                    <p className="break-all font-mono text-xs text-slate-600">
                      sha256: {preview.source_sha256}
                    </p>
                    <p className="mt-1 text-sm text-slate-700">
                      {summary.components} cấu kiện · {summary.segments} phân đoạn
                      · {summary.workLinks} liên kết công việc
                    </p>
                  </div>

                  {summary.conflicts > 0 ? (
                    <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900">
                      <p className="font-semibold">
                        {summary.conflicts} xung đột — không thể nhập
                      </p>
                      <ul className="mt-2 list-disc space-y-1 pl-5">
                        {preview.conflicts.map((conflict, index) => (
                          <li key={`${index}-${conflict}`}>{conflict}</li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="rounded-lg border border-green-200 bg-green-50 p-2 text-sm text-green-800">
                      Không có xung đột trong preview này.
                    </p>
                  )}

                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <label className="text-xs font-semibold text-slate-700">
                      Tìm trong preview
                      <input
                        className={`${FIELD_CLASS} mt-1`}
                        value={filters.query}
                        placeholder="mã, mã gốc, alias, dòng nguồn…"
                        onChange={(event) =>
                          updateFilter({ query: event.target.value })
                        }
                      />
                    </label>
                    <label className="text-xs font-semibold text-slate-700">
                      Khu
                      <select
                        className={`${FIELD_CLASS} mt-1`}
                        value={filters.zone}
                        onChange={(event) =>
                          updateFilter({ zone: event.target.value })
                        }
                      >
                        <option value="">Tất cả khu</option>
                        {zones.map((zone) => (
                          <option key={zone} value={zone}>
                            {zone}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-xs font-semibold text-slate-700">
                      Loại
                      <select
                        className={`${FIELD_CLASS} mt-1`}
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
                    <label className="text-xs font-semibold text-slate-700">
                      Phân đoạn
                      <select
                        className={`${FIELD_CLASS} mt-1`}
                        value={filters.segment}
                        onChange={(event) =>
                          updateFilter({ segment: event.target.value })
                        }
                      >
                        <option value="">Tất cả phân đoạn</option>
                        {segmentNumbers.map((number) => (
                          <option key={number} value={number}>
                            PĐ {number}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-xs font-semibold text-slate-700">
                      Phạm vi
                      <select
                        className={`${FIELD_CLASS} mt-1`}
                        value={filters.scope}
                        onChange={(event) =>
                          updateFilter({ scope: event.target.value })
                        }
                      >
                        <option value="">Tất cả phạm vi</option>
                        <option value="DESIGN_SCOPE">Theo thiết kế</option>
                        <option value="ADDITIONAL_SCOPE">
                          Phát sinh sửa chữa
                        </option>
                      </select>
                    </label>
                    <label className="text-xs font-semibold text-slate-700">
                      Xác minh danh mục
                      <select
                        className={`${FIELD_CLASS} mt-1`}
                        value={filters.verification}
                        onChange={(event) =>
                          updateFilter({ verification: event.target.value })
                        }
                      >
                        <option value="">Tất cả trạng thái</option>
                        <option value="NEEDS_REVIEW">Chờ duyệt</option>
                      </select>
                    </label>
                  </div>

                  <p className="text-xs text-slate-600">
                    Hiển thị {visible.length}/{filtered.length} cấu kiện (tổng{" "}
                    {summary.components}).
                  </p>
                  <div className="space-y-2">
                    {visible.map((component) => (
                      <CandidateCard
                        key={`${component.source_id}-${component.source_row}`}
                        component={component}
                      />
                    ))}
                    {filtered.length === 0 ? (
                      <p className="rounded-lg border border-gray-200 p-3 text-sm text-slate-600">
                        Không có dòng khớp bộ lọc.
                      </p>
                    ) : null}
                  </div>
                  {visible.length < filtered.length ? (
                    <button
                      type="button"
                      className={`${SECONDARY_BUTTON} w-full`}
                      onClick={() =>
                        setVisibleLimit((current) => current + PAGE_SIZE)
                      }
                    >
                      Hiển thị thêm{" "}
                      {Math.min(PAGE_SIZE, filtered.length - visible.length)} dòng
                    </button>
                  ) : null}

                  <details className="rounded-lg border border-gray-200 bg-white p-2">
                    <summary
                      className={`flex min-h-11 cursor-pointer items-center justify-between gap-2 text-sm font-semibold text-slate-800 ${FOCUS_RING}`}
                    >
                      <span>Phân đoạn trong preview ({summary.segments})</span>
                    </summary>
                    <ul className="mt-2 space-y-1 text-xs text-slate-700">
                      {preview.segments.map((segment) => (
                        <li key={segment.source_id} className="font-mono">
                          {segment.zone} · PĐ {segment.number} ·{" "}
                          {segment.source_id}
                        </li>
                      ))}
                    </ul>
                  </details>

                  <details className="rounded-lg border border-gray-200 bg-white p-2">
                    <summary
                      className={`flex min-h-11 cursor-pointer items-center justify-between gap-2 text-sm font-semibold text-slate-800 ${FOCUS_RING}`}
                    >
                      <span>Liên kết công việc ({summary.workLinks})</span>
                    </summary>
                    <div className="mt-2 max-h-80 space-y-1 overflow-auto text-xs">
                      {preview.work_links.slice(0, workLinkLimit).map((link) => (
                        <div
                          key={`${link.source_id}-${link.dm_row}`}
                          className="rounded border border-gray-100 p-2"
                        >
                          <p className="break-all font-mono">
                            {link.code} · DM dòng {link.dm_row} · seed dòng{" "}
                            {link.seed_row} · {link.source_id}
                          </p>
                          <p className="text-slate-700">{link.work}</p>
                          <p className="break-all text-slate-600">
                            {link.raw_location}
                          </p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-2 space-y-2">
                      <p className="text-xs text-slate-600">
                        Đang xem {Math.min(workLinkLimit, preview.work_links.length)}
                        /{preview.work_links.length} liên kết.
                      </p>
                      {workLinkLimit < preview.work_links.length ? (
                        <div className="flex flex-col gap-2 sm:flex-row">
                          <button
                            type="button"
                            className={`${SECONDARY_BUTTON} flex-1`}
                            onClick={() =>
                              setWorkLinkLimit((current) => current + PAGE_SIZE)
                            }
                          >
                            Hiển thị thêm{" "}
                            {Math.min(
                              PAGE_SIZE,
                              preview.work_links.length - workLinkLimit,
                            )}{" "}
                            liên kết
                          </button>
                          <button
                            type="button"
                            className={`${SECONDARY_BUTTON} flex-1`}
                            onClick={() =>
                              setWorkLinkLimit(preview.work_links.length)
                            }
                          >
                            Hiển thị tất cả
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </details>

                  <div className="rounded-lg border border-amber-300 bg-amber-50 p-3">
                    <p className="text-sm font-semibold text-amber-950">
                      Preview được gửi nguyên bản
                    </p>
                    <p className="mt-1 text-xs text-amber-950">
                      Muốn sửa, hãy sửa workbook rồi tạo lại preview. Nếu còn
                      xung đột, nút nhập bị khóa.
                    </p>
                    <label className="mt-3 flex min-h-11 items-start gap-2 text-sm text-amber-950">
                      <input
                        type="checkbox"
                        className={`mt-1 h-5 w-5 rounded border-gray-400 ${FOCUS_RING}`}
                        checked={confirmed}
                        disabled={!canCommit || busy !== null}
                        onChange={(event) => setConfirmed(event.target.checked)}
                      />
                      <span>
                        Tôi đã kiểm tra workbook và preview khớp nhau, và xác nhận
                        nhập {summary.components} cấu kiện / {summary.segments}{" "}
                        phân đoạn.
                      </span>
                    </label>
                    <button
                      type="button"
                      className={`mt-3 min-h-11 w-full rounded-lg bg-green-700 px-4 text-sm font-semibold text-white active:bg-green-800 disabled:cursor-not-allowed disabled:bg-gray-300 ${FOCUS_RING}`}
                      disabled={!canCommit || !confirmed || busy !== null}
                      onClick={() => void handleCommit()}
                    >
                      {busy === "commit"
                        ? "Đang nhập danh mục…"
                        : "Xác nhận nhập danh mục"}
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          </details>

          <details className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <summary className={DETAILS_SUMMARY}>
              <span className="text-base font-semibold text-slate-900">
                Tạo cấu kiện thủ công
              </span>
              <span className="text-xs font-normal text-slate-600">
                Chỉ dùng phân đoạn đã có
              </span>
            </summary>
            <div className="border-t border-gray-100 p-3">
              <p className="text-xs text-slate-600">
                UI không tạo nguồn, bản vẽ hay nghiệm thu; máy chủ gán trạng thái
                xác minh.
              </p>
              <form
                className="mt-3 space-y-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  void handleCreateManual();
                }}
              >
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <label className="text-xs font-semibold text-slate-700">
                    Phân đoạn
                    <select
                      required
                      className={`${FIELD_CLASS} mt-1`}
                      value={manual.segment_id}
                      disabled={manualBusy || segments.length === 0}
                      onChange={(event) =>
                        setManual((current) => ({
                          ...current,
                          segment_id: event.target.value,
                        }))
                      }
                    >
                      <option value="">— Chọn phân đoạn đã có —</option>
                      {segments.map((segment) => (
                        <option key={segment.id} value={segment.id}>
                          {segmentLabel(segment)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-xs font-semibold text-slate-700">
                    Loại
                    <select
                      required
                      className={`${FIELD_CLASS} mt-1`}
                      value={manual.type}
                      disabled={manualBusy}
                      onChange={(event) =>
                        setManual((current) => ({
                          ...current,
                          type: event.target
                            .value as ManualComponentDraft["type"],
                        }))
                      }
                    >
                      <option value="">— Chọn loại —</option>
                      <option value="pile">Cọc (pile)</option>
                      <option value="beam">Dầm (beam)</option>
                    </select>
                  </label>
                  <label className="text-xs font-semibold text-slate-700">
                    Mã gốc (raw_code)
                    <input
                      required
                      maxLength={120}
                      className={`${FIELD_CLASS} mt-1`}
                      value={manual.raw_code}
                      disabled={manualBusy}
                      placeholder="Ví dụ I40-42"
                      onChange={(event) =>
                        setManual((current) => ({
                          ...current,
                          raw_code: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="text-xs font-semibold text-slate-700">
                    Mã chuẩn (canonical_code)
                    <input
                      required
                      maxLength={120}
                      className={`${FIELD_CLASS} mt-1`}
                      value={manual.canonical_code}
                      disabled={manualBusy}
                      placeholder="Ví dụ I-40-42"
                      onChange={(event) =>
                        setManual((current) => ({
                          ...current,
                          canonical_code: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="text-xs font-semibold text-slate-700">
                    Phạm vi
                    <select
                      required
                      className={`${FIELD_CLASS} mt-1`}
                      value={manual.scope}
                      disabled={manualBusy}
                      onChange={(event) =>
                        setManual((current) => ({
                          ...current,
                          scope: event.target
                            .value as ManualComponentDraft["scope"],
                        }))
                      }
                    >
                      <option value="">— Chọn phạm vi —</option>
                      <option value="DESIGN_SCOPE">Theo thiết kế</option>
                      <option value="ADDITIONAL_SCOPE">
                        Phát sinh sửa chữa
                      </option>
                    </select>
                  </label>
                </div>

                {segments.length === 0 ? (
                  <p className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-950">
                    Chưa có phân đoạn trong công trình. Nhập workbook có phân đoạn
                    trước khi tạo cấu kiện thủ công.
                  </p>
                ) : null}
                {manualError ? (
                  <p
                    role="alert"
                    className="rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-800"
                  >
                    {manualError}
                  </p>
                ) : null}
                {manualMessage ? (
                  <p
                    role="status"
                    className="rounded-lg border border-green-200 bg-green-50 p-2 text-sm text-green-800"
                  >
                    {manualMessage}
                  </p>
                ) : null}
                <button
                  type="submit"
                  className={`${PRIMARY_BUTTON} w-full`}
                  disabled={manualBusy || segments.length === 0}
                >
                  {manualBusy ? "Đang tạo cấu kiện…" : "Tạo cấu kiện"}
                </button>
              </form>
            </div>
          </details>
        </>
      )}
      </div>
    </section>
  );
}
