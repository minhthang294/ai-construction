import { useCallback, useEffect, useMemo, useState } from "react";
import {
  deleteDraft,
  enqueue,
  loadDraft,
  loadViewCache,
  removeQueue,
  reportQueueId,
  saveDraft,
  saveViewCache,
} from "../lib/offlineDb";
import { useOfflineSync } from "../hooks/useOfflineSync";
import {
  ApiError,
  getDailyReport,
  getOrganizations,
  getWorkItems,
  listPhotos,
  patchPhoto,
  saveDailyReport,
} from "../lib/api";
import { presetToManpowerEntry } from "../lib/manpower";
import { addDaysISO } from "../lib/datetime";
import {
  decideViewSource,
  formatCachedAt,
  makeViewCacheRecord,
  offlineDataLabel,
} from "../lib/viewCache";
import ManpowerTable from "../components/ManpowerTable";
import WorkLogForm from "../components/WorkLogForm";
import NextDayPlanForm from "../components/NextDayPlanForm";
import PhotoCapture from "../components/PhotoCapture";
import ExportPanel from "../components/ExportPanel";
import ManpowerPresets from "../components/ManpowerPresets";
import SiteNotesForm from "../components/SiteNotesForm";
import OfflineQueuePanel from "../components/OfflineQueuePanel";
import AcceptanceHistoryPanel from "../components/AcceptanceHistoryPanel";
import { EMPTY_PHOTO_FILTERS } from "../types";
import type {
  DailyReport,
  DailyReportInput,
  DailyWorkLog,
  ManpowerEntry,
  NextDayPlan,
  Organization,
  PhotoFilters,
  ReportStatus,
  SiteNotes,
  SitePhoto,
  WorkItem,
} from "../types";

type Props = {
  projectId: string;
  date: string;
  /** Optional navigation hook; the shared app shell can route the new date. */
  onDateChange?: (date: string) => void;
  /** Optional app-shell navigation to the Nghiệm thu page. */
  onOpenAcceptance?: () => void;
};

function mergePhotos(previous: SitePhoto[], incoming: SitePhoto[]): SitePhoto[] {
  const byId = new Map(previous.map((photo) => [photo.id, photo]));
  incoming.forEach((photo) => byId.set(photo.id, photo));
  return Array.from(byId.values()).sort((a, b) =>
    b.upload_time.localeCompare(a.upload_time),
  );
}

function displayDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export default function SiteReportPage({
  projectId,
  date,
  onDateChange,
  onOpenAcceptance,
}: Props) {
  const [report, setReport] = useState<DailyReport | null>(null);
  const [manpower, setManpower] = useState<ManpowerEntry[]>([]);
  const [workLogs, setWorkLogs] = useState<DailyWorkLog[]>([]);
  const [plans, setPlans] = useState<NextDayPlan[]>([]);
  const [notes, setNotes] = useState("");
  const [siteNotes, setSiteNotes] = useState<SiteNotes>({});
  const [status, setStatus] = useState<ReportStatus>("draft");
  const [photos, setPhotos] = useState<SitePhoto[]>([]);
  const [photoFilters, setPhotoFilters] = useState<PhotoFilters>(EMPTY_PHOTO_FILTERS);
  const [workItems, setWorkItems] = useState<WorkItem[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [offlineCacheAt, setOfflineCacheAt] = useState<number | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<number | null>(null);

  const draftKey = `${projectId}:${date}`;
  const tomorrow = addDaysISO(date, 1);
  const { online, pending, failed, queue, syncing, revision, syncNow, discard } =
    useOfflineSync(projectId);

  const buildBody = useCallback(
    (): DailyReportInput => ({
      status,
      notes: notes.trim() ? notes : null,
      site_notes: siteNotes,
      manpower,
      work_logs: workLogs,
      next_day_plans: plans,
    }),
    [manpower, notes, plans, siteNotes, status, workLogs],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoaded(false);
      setMessage(null);
      setOfflineCacheAt(null);
      setLastSyncedAt(null);
      let remote: DailyReport | null = null;
      let serverFailed = false;
      try {
        remote = await getDailyReport(projectId, date);
      } catch {
        serverFailed = true;
      }
      let draft;
      try {
        draft = await loadDraft(draftKey);
      } catch {
        draft = undefined;
      }
      let cached;
      try {
        cached = await loadViewCache(projectId, date);
      } catch {
        cached = undefined;
      }
      if (cancelled) return;

      const source = decideViewSource(serverFailed, cached);
      const cachedReport =
        source === "cache" && cached && cached.report && typeof cached.report === "object"
          ? (cached.report as DailyReport)
          : null;
      const baseReport = remote ?? cachedReport;
      const draftIsNewer =
        draft &&
        (!baseReport || draft.updatedAt > Date.parse(baseReport.updated_at) + 1000);

      if (draftIsNewer && draft) {
        const payload = draft.payload as Partial<DailyReportInput>;
        setManpower(Array.isArray(payload.manpower) ? payload.manpower : []);
        setWorkLogs(Array.isArray(payload.work_logs) ? payload.work_logs : []);
        setPlans(Array.isArray(payload.next_day_plans) ? payload.next_day_plans : []);
        setNotes(payload.notes ?? "");
        setSiteNotes(payload.site_notes ?? {});
        setStatus(payload.status === "reviewed" ? "reviewed" : "draft");
      } else if (baseReport) {
        setManpower(baseReport.manpower);
        setWorkLogs(baseReport.work_logs);
        setPlans(baseReport.next_day_plans);
        setNotes(baseReport.notes ?? "");
        setSiteNotes(baseReport.site_notes ?? {});
        setStatus(baseReport.status);
      } else {
        setManpower([]);
        setWorkLogs([]);
        setPlans([]);
        setNotes("");
        setSiteNotes({});
        setStatus("draft");
      }
      setReport(baseReport);

      if (source === "cache" && cached) {
        setOfflineCacheAt(cached.cachedAt);
        setPhotos(cached.photos as SitePhoto[]);
        setWorkItems(cached.workItems as WorkItem[]);
        setOrganizations([]);
        setMessage(
          `Đang dùng bản offline. ${offlineDataLabel(cached.cachedAt)}.`,
        );
      } else if (!baseReport) {
        setPhotos([]);
        setWorkItems([]);
        if (serverFailed) {
          setMessage("Không tải được báo cáo từ máy chủ; chưa có bản lưu trên thiết bị.");
        }
      }

      let loadedWorkItems: WorkItem[] =
        source === "cache" && cached ? (cached.workItems as WorkItem[]) : [];
      let loadedPhotos: SitePhoto[] =
        source === "cache" && cached ? (cached.photos as SitePhoto[]) : [];

      if (!serverFailed && remote) {
        try {
          loadedWorkItems = await getWorkItems(projectId);
          if (!cancelled) setWorkItems(loadedWorkItems);
        } catch {
          loadedWorkItems =
            source === "cache" && cached ? (cached.workItems as WorkItem[]) : [];
          if (!cancelled) setWorkItems(loadedWorkItems);
        }

        try {
          const orgs = await getOrganizations(projectId);
          if (!cancelled) setOrganizations(orgs);
        } catch {
          if (!cancelled) setOrganizations([]);
        }

        try {
          loadedPhotos = await listPhotos(projectId, remote.id);
          if (!cancelled) setPhotos(loadedPhotos);
        } catch {
          loadedPhotos = cached?.photos ? (cached.photos as SitePhoto[]) : [];
          if (!cancelled) setPhotos(loadedPhotos);
        }

        if (!cancelled) {
          setLastSyncedAt(Date.now());
          try {
            await saveViewCache(
              makeViewCacheRecord({
                projectId,
                date,
                report: remote,
                photos: loadedPhotos,
                workItems: loadedWorkItems,
              }),
            );
          } catch {
            // Storage quota/private mode must not break the report view.
          }
        }
      } else if (source !== "cache") {
        try {
          const orgs = await getOrganizations(projectId);
          if (!cancelled) setOrganizations(orgs);
        } catch {
          if (!cancelled) setOrganizations([]);
        }
      }

      if (!cancelled) setLoaded(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, date, draftKey]);

  // Debounced local draft: survives reloads and offline use.
  useEffect(() => {
    if (!loaded) return;
    const timer = window.setTimeout(() => {
      void saveDraft({
        key: draftKey,
        projectId,
        date,
        payload: buildBody(),
        updatedAt: Date.now(),
      }).catch(() => undefined);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [loaded, buildBody, draftKey, projectId, date]);

  useEffect(() => {
    if (!loaded || revision === 0) return;
    let cancelled = false;
    (async () => {
      try {
        const remote = await getDailyReport(projectId, date);
        if (cancelled) return;
        if (!remote) {
          if (!cancelled) setPhotos([]);
          return;
        }
        setReport(remote);
        setLastSyncedAt(Date.now());
        setOfflineCacheAt(null);
      } catch {
        // The next sync tick or manual refresh will retry.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [revision, loaded, projectId, date]);

  useEffect(() => {
    if (!report?.id) return;
    let cancelled = false;
    (async () => {
      try {
        const filtered = await listPhotos(projectId, report.id, photoFilters);
        if (!cancelled) setPhotos(filtered);
      } catch {
        // Keep the current list if the filter request fails (offline).
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, report?.id, photoFilters, revision]);

  async function persistLocalDraft() {
    try {
      await saveDraft({
        key: draftKey,
        projectId,
        date,
        payload: buildBody(),
        updatedAt: Date.now(),
      });
    } catch {
      // IndexedDB may be unavailable (private mode); server save still works.
    }
  }

  async function queueReportSave(): Promise<boolean> {
    try {
      await enqueue({
        id: reportQueueId(projectId, date),
        projectId,
        kind: "report",
        payload: { date, body: buildBody() },
        createdAt: Date.now(),
        attempts: 0,
      });
      return true;
    } catch {
      return false;
    }
  }

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    await persistLocalDraft();
    const body = buildBody();

    if (!online) {
      const queued = await queueReportSave();
      setMessage(
        queued
          ? "Đã lưu nháp trên thiết bị. Báo cáo sẽ đồng bộ khi có mạng."
          : "Không lưu được hàng đợi offline trên thiết bị này.",
      );
      setSaving(false);
      return;
    }

    try {
      const saved = await saveDailyReport(projectId, date, body);
      setReport(saved);
      setLastSyncedAt(Date.now());
      setOfflineCacheAt(null);
      try {
        await removeQueue(reportQueueId(projectId, date));
        await deleteDraft(draftKey);
      } catch {
        // Non-fatal cleanup failure.
      }

      // Photos captured before the first save are linked to this report now.
      const unlinked = photos.filter((photo) => !photo.report_id);
      let nextPhotos = photos;
      if (unlinked.length > 0) {
        const linked = await Promise.all(
          unlinked.map((photo) =>
            patchPhoto(projectId, photo.id, { report_id: saved.id }).catch(
              () => photo,
            ),
          ),
        );
        nextPhotos = mergePhotos(photos, linked);
        setPhotos(nextPhotos);
      }
      const filtersActive = Object.values(photoFilters).some(Boolean);
      if (!filtersActive) {
        try {
          await saveViewCache(
            makeViewCacheRecord({
              projectId,
              date,
              report: saved,
              photos: nextPhotos,
              workItems,
            }),
          );
        } catch {
          // Storage quota/private mode must not fail the save.
        }
      }
      setMessage("Đã lưu báo cáo.");
    } catch (error) {
      const isValidationError = error instanceof ApiError && error.status < 500;
      if (isValidationError) {
        setMessage(error.message);
      } else {
        const queued = await queueReportSave();
        setMessage(
          queued
            ? "Mất kết nối. Đã lưu nháp và xếp hàng đồng bộ."
            : "Mất kết nối và không lưu được hàng đợi offline.",
        );
      }
    } finally {
      setSaving(false);
    }
  }

  const dateLabel = useMemo(() => displayDate(date), [date]);
  const dayWorkItems = useMemo(() => {
    const ids = new Set<string>();
    workLogs.forEach((entry) => {
      if (entry.work_item_id) ids.add(entry.work_item_id);
    });
    plans.forEach((entry) => {
      if (entry.work_item_id) ids.add(entry.work_item_id);
    });
    return workItems.filter((item) => ids.has(item.id));
  }, [workLogs, plans, workItems]);

  return (
    <div className="mx-auto min-h-screen max-w-2xl space-y-4 bg-gray-100 p-3 pb-28">
      <header className="sticky top-0 z-20 -mx-3 border-b border-gray-200 bg-gray-100/95 px-3 py-2 backdrop-blur">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h1 className="text-xl font-bold">Báo cáo ngày</h1>
            {onDateChange ? (
              <div className="mt-1 flex items-center gap-2">
                <button
                  type="button"
                  aria-label="Ngày trước"
                  className="min-h-8 rounded border border-gray-300 bg-white px-2 text-sm"
                  onClick={() => onDateChange(addDaysISO(date, -1))}
                >
                  ‹
                </button>
                <input
                  type="date"
                  className="min-h-9 rounded border border-gray-300 bg-white px-2 text-sm"
                  value={date}
                  onChange={(event) => {
                    if (event.target.value) onDateChange(event.target.value);
                  }}
                />
                <button
                  type="button"
                  aria-label="Ngày sau"
                  className="min-h-8 rounded border border-gray-300 bg-white px-2 text-sm"
                  onClick={() => onDateChange(addDaysISO(date, 1))}
                >
                  ›
                </button>
              </div>
            ) : (
              <p className="text-sm capitalize text-gray-600">{dateLabel}</p>
            )}
          </div>
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              online ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800"
            }`}
          >
            {online ? "Online" : "Offline"}
            {pending > 0 ? ` · ${pending} chờ` : ""}
            {failed > 0 ? ` · ${failed} lỗi` : ""}
          </span>
        </div>
      </header>

      {(offlineCacheAt != null || lastSyncedAt != null) && (
        <div
          className={`rounded-lg px-3 py-2 text-xs ${
            offlineCacheAt != null
              ? "bg-amber-50 text-amber-800"
              : "bg-green-50 text-green-800"
          }`}
        >
          {offlineCacheAt != null
            ? `Đang dùng bản offline · ${offlineDataLabel(offlineCacheAt)}`
            : `Đã đồng bộ lúc ${formatCachedAt(lastSyncedAt as number)}`}
        </div>
      )}

      {!online && (
        <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          Đang offline. Mọi thay đổi được lưu trên thiết bị và tự đồng bộ khi có mạng.
        </div>
      )}

      {message && (
        <div className="whitespace-pre-wrap rounded-xl bg-white p-3 text-sm shadow-sm">
          {message}
        </div>
      )}

      <section className="space-y-3 rounded-xl bg-white p-3 shadow-sm">
        <div>
          <label className="block text-sm font-medium text-gray-700">Ghi chú</label>
          <textarea
            className="mt-1 min-h-20 w-full rounded-lg border border-gray-300 px-3 py-2 text-base"
            placeholder="Thời tiết, an toàn, vướng mắc chung…"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </div>
        <div>
          <p className="mb-1 text-sm font-medium text-gray-700">Trạng thái báo cáo</p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              className={`min-h-11 rounded-lg border px-3 text-sm font-medium ${
                status === "draft"
                  ? "border-gray-800 bg-gray-800 text-white"
                  : "border-gray-300 bg-white text-gray-700"
              }`}
              onClick={() => setStatus("draft")}
            >
              Nháp
            </button>
            <button
              type="button"
              className={`min-h-11 rounded-lg border px-3 text-sm font-medium ${
                status === "reviewed"
                  ? "border-green-700 bg-green-700 text-white"
                  : "border-gray-300 bg-white text-gray-700"
              }`}
              onClick={() => setStatus("reviewed")}
            >
              Đã duyệt
            </button>
          </div>
          <p className="mt-1 text-xs text-gray-500">
            Chỉ báo cáo “Đã duyệt” mới được xuất file.
          </p>
        </div>
      </section>

      <SiteNotesForm notes={siteNotes} onChange={setSiteNotes} />

      <ManpowerTable
        entries={manpower}
        onChange={setManpower}
        organizations={organizations}
      />
      <ManpowerPresets
        projectId={projectId}
        organizations={organizations}
        onUse={(preset) =>
          setManpower((current) => [...current, presetToManpowerEntry(preset)])
        }
      />
      <WorkLogForm entries={workLogs} onChange={setWorkLogs} workItems={workItems} />
      <NextDayPlanForm
        entries={plans}
        onChange={setPlans}
        defaultDate={tomorrow}
        workItems={workItems}
      />

      <AcceptanceHistoryPanel
        projectId={projectId}
        workItems={dayWorkItems.map((item) => ({
          id: item.id,
          code: item.code,
          name: item.name,
        }))}
        onOpenAcceptance={onOpenAcceptance}
      />

      <PhotoCapture
        projectId={projectId}
        reportId={report?.id ?? null}
        reportDate={date}
        photos={photos}
        online={online}
        pendingCount={pending}
        workItems={workItems}
        filters={photoFilters}
        onFiltersChange={setPhotoFilters}
        onUploaded={(uploaded) =>
          setPhotos((previous) => mergePhotos(previous, uploaded))
        }
        onQueued={() => setMessage("Ảnh đã xếp hàng đồng bộ.")}
      />

      <ExportPanel
        projectId={projectId}
        date={date}
        report={report}
        onMessage={setMessage}
      />

      <OfflineQueuePanel
        projectId={projectId}
        items={queue}
        disabled={syncing}
        onDiscard={discard}
        onMessage={setMessage}
      />

      {pending > 0 && (
        <button
          type="button"
          className="min-h-11 w-full rounded-lg border border-blue-300 bg-blue-50 text-sm font-medium text-blue-800"
          disabled={syncing || !online}
          onClick={() => void syncNow()}
        >
          {syncing ? "Đang đồng bộ…" : `Đồng bộ ngay (${pending})`}
        </button>
      )}

      <p className="pb-2 text-center text-xs text-gray-500">
        Ảnh gốc được bảo toàn. Không tự động gửi Zalo. Dữ liệu nhân lực 0 khác “chưa rõ”.
      </p>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-gray-200 bg-white/95 p-3 backdrop-blur">
        <div className="mx-auto flex max-w-2xl gap-2">
          <button
            type="button"
            className="min-h-12 flex-1 rounded-xl bg-green-700 px-4 text-base font-semibold text-white active:bg-green-800 disabled:opacity-60"
            disabled={saving}
            onClick={() => void handleSave()}
          >
            {saving ? "Đang lưu…" : "Lưu báo cáo"}
          </button>
          <button
            type="button"
            className="min-h-12 rounded-xl border border-gray-300 px-4 text-sm font-medium text-gray-800 disabled:opacity-40"
            disabled={!online || syncing}
            onClick={() => void syncNow()}
          >
            {syncing ? "Đang đồng bộ…" : "Đồng bộ"}
          </button>
        </div>
      </div>
    </div>
  );
}
