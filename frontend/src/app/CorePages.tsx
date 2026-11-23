import { useEffect, useMemo, useState, type CSSProperties } from "react";
import PageHeader from "./PageHeader";
import ConstructionProgressChart, { type ConstructionProgressSummary } from "./ConstructionProgressChart";
import LatestDayCard from "./LatestDayCard";
import SegmentProgressBars from "./SegmentProgressBars";
import type { LatestDay, SegmentProgress } from "./overviewFormat";
import ConstructionBatchSelector from "../features/site/components/ConstructionBatchSelector";
import {
  useConstructionBatch,
  useConstructionBatches,
} from "../features/site/hooks/useConstructionBatch";
import { listComponentProgress } from "../features/site/lib/api";
import type { ProgressRow } from "../features/site/lib/componentProgress";
import {
  AcceptanceIcon,
  CameraIcon,
  CheckCircleIcon,
  ClockIcon,
  DocumentsIcon,
  WorkIcon,
} from "./AppIcons";

export type Project = { id: string; name: string; client?: string; location?: string; report_title?: string; can_delete?: boolean };
type WorkItem = { id: string; code: string; name: string; location?: string; component?: string; status: string };
type PreviewItem = Omit<WorkItem, "id" | "status"> & { source_row: number };
const workStatuses = { planned: "Dự kiến", in_progress: "Đang thi công", completed: "Hoàn thành", pending_acceptance: "Chờ nghiệm thu", rectify: "Cần khắc phục" } as const;

export function groupWorkItems(items: WorkItem[]) {
  const groups = new Map<string, Map<string, WorkItem[]>>();
  for (const item of items) {
    const title = item.name.trim();
    const phase = /^(đục|phá)/i.test(title) ? "Đục phá" : /^(tẩy|mài)/i.test(title) ? "Xử lý bề mặt" : /^(vệ sinh|quét)/i.test(title) ? "Vệ sinh và kết dính" : /^(khoan|cấy)/i.test(title) ? "Khoan cấy cốt thép" : /^(lắp|bơm)/i.test(title) ? "Lắp đặt và bơm vữa" : "Công việc khác";
    const sameName = groups.get(phase) ?? new Map<string, WorkItem[]>();
    const key = title.toLocaleLowerCase("vi");
    sameName.set(key, [...(sameName.get(key) ?? []), item]);
    groups.set(phase, sameName);
  }
  return groups;
}

export async function request(path: string, token: string, init?: RequestInit) {
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`/api/v1${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export function ProjectSetup({
  token,
  projects,
  currentProjectId,
  onCreated,
  onUpdated,
  onDeleted,
}: {
  token: string;
  projects: Project[];
  currentProjectId?: string;
  onCreated: (project: Project) => void;
  onUpdated: (project: Project) => void;
  onDeleted: (id: string) => void;
}) {
  const [name, setName] = useState("");
  const [client, setClient] = useState("");
  const [location, setLocation] = useState("");
  const [reportTitle, setReportTitle] = useState("");
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  async function create(event: React.FormEvent) {
    event.preventDefault();
    try {
      const project = await request("/projects", token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, client, location, report_title: reportTitle || null }) });
      onCreated(project);
      setName(""); setClient(""); setLocation(""); setReportTitle(""); setError("");
    } catch (cause) { setError((cause as Error).message); }
  }
  function edit(project: Project) {
    setEditingId(project.id); setName(project.name); setClient(project.client || ""); setLocation(project.location || ""); setReportTitle(project.report_title || ""); setError("");
  }
  function reset() {
    setEditingId(""); setName(""); setClient(""); setLocation(""); setReportTitle(""); setError("");
  }
  async function update(event: React.FormEvent) {
    event.preventDefault();
    try {
      const project = await request(`/projects/${editingId}`, token, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, client, location, report_title: reportTitle }) });
      onUpdated(project); reset(); setError("");
    } catch (cause) { setError((cause as Error).message); }
  }
  async function remove(project: Project) {
    if (deleting || !window.confirm(`Xóa công trình “${project.name}” khỏi danh sách? Hồ sơ và lịch sử của công trình sẽ được lưu lại.`)) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await request(`/projects/${project.id}`, token, { method: "DELETE" });
      if (editingId === project.id) reset();
      onDeleted(project.id);
    } catch (cause) {
      setDeleteError((cause as Error).message);
    } finally {
      setDeleting(false);
    }
  }
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Quản trị"
        title="Công trình"
        description="Thông tin công trình được dùng lại cho báo cáo ngày, phiếu yêu cầu nghiệm thu và biên bản nghiệm thu."
      />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(22rem,.9fr)] lg:items-start">
        <section className="app-card app-card-pad">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-slate-950">Danh sách công trình</h2>
              <p className="mt-1 text-xs text-slate-500">{projects.length} công trình đang quản lý</p>
            </div>
            <button type="button" className="app-button app-button-secondary px-3" onClick={reset}>
              + Tạo mới
            </button>
          </div>
          {deleteError && <p role="alert" className="mt-3 text-sm text-red-700">{deleteError}</p>}
          <div className="mt-4 space-y-2">
            {projects.length === 0 && (
              <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
                Chưa có công trình. Tạo công trình đầu tiên ở biểu mẫu bên cạnh.
              </p>
            )}
            {projects.map((project) => {
              const active = project.id === currentProjectId;
              return (
                <article
                  key={project.id}
                  className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3.5 ${active ? "border-[#405e9b]/35 bg-[#405e9b]/5" : "border-slate-200 bg-white"}`}
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-slate-900">{project.name}</h3>
                      {active && <span className="app-badge border-[#405e9b]/25 bg-white text-[#35507f]">Đang chọn</span>}
                    </div>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      {project.client || "Chưa có chủ đầu tư"} · {project.location || "Chưa có địa điểm"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => edit(project)} className="app-button app-button-secondary min-h-10 px-3">
                      Sửa
                    </button>
                    {project.can_delete && (
                      <button type="button" disabled={deleting} onClick={() => void remove(project)} className="app-button app-button-danger min-h-10 px-3">
                        Xóa công trình
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className="app-card app-card-pad lg:sticky lg:top-24">
          <h2 className="text-base font-semibold text-slate-950">
            {editingId ? "Sửa thông tin công trình" : "Tạo công trình"}
          </h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Các trường này được điền sẵn vào báo cáo và phiếu nghiệm thu.
          </p>
          <form onSubmit={editingId ? update : create} className="mt-4 space-y-4">
            <label className="app-label">
              Tên công trình
              <input className="app-input mt-1.5" value={name} onChange={(event) => setName(event.target.value)} required />
            </label>
            <label className="app-label">
              Chủ đầu tư
              <input className="app-input mt-1.5" value={client} onChange={(event) => setClient(event.target.value)} />
            </label>
            <label className="app-label">
              Địa điểm
              <input className="app-input mt-1.5" value={location} onChange={(event) => setLocation(event.target.value)} />
            </label>
            <label className="app-label">
              Tiêu đề báo cáo <span className="font-normal text-slate-400">(tùy chọn)</span>
              <input className="app-input mt-1.5" value={reportTitle} onChange={(event) => setReportTitle(event.target.value)} />
            </label>
            {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
            <div className="flex flex-wrap gap-2">
              <button className="app-button app-button-primary flex-1">{editingId ? "Lưu thay đổi" : "Tạo công trình"}</button>
              {editingId && <button type="button" className="app-button app-button-secondary" onClick={reset}>Hủy</button>}
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}

export function WorkItemList({ token, projectId }: { token: string; projectId: string }) {
  const [items, setItems] = useState<WorkItem[]>([]);
  const [preview, setPreview] = useState<PreviewItem[]>([]);
  const [name, setName] = useState("");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { request(`/projects/${projectId}/work-items`, token).then(setItems).catch((cause) => setError(cause.message)); }, [projectId, token]);
  async function previewFile(file?: File) {
    if (!file) return;
    const form = new FormData(); form.append("file", file);
    try {
      const result = await request(`/projects/${projectId}/work-items/import-preview`, token, { method: "POST", body: form });
      setPreview(result.items); setError("");
    } catch (cause) { setError((cause as Error).message); }
  }
  async function importItems() {
    setSaving(true);
    try {
      await request(`/projects/${projectId}/work-items/import`, token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items: preview }) });
      setItems(await request(`/projects/${projectId}/work-items`, token));
      setPreview([]); setError("");
    } catch (cause) { setError((cause as Error).message); }
    finally { setSaving(false); }
  }
  async function createItem(event: React.FormEvent) {
    event.preventDefault();
    try {
      if (items.some((item) => item.name.trim().toLocaleLowerCase("vi") === name.trim().toLocaleLowerCase("vi"))) {
        setError("Công việc này đã có trong danh mục.");
        return;
      }
      const item = await request(`/projects/${projectId}/work-items`, token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: `manual-${crypto.randomUUID()}`, name: name.trim() }) });
      setItems((current) => [...current, item].sort((a, b) => a.code.localeCompare(b.code)));
      setName(""); setError("");
    } catch (cause) { setError((cause as Error).message); }
  }
  async function changeStatus(item: WorkItem, status: string) {
    try {
      const changed = await request(`/projects/${projectId}/work-items/${item.id}`, token, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) });
      setItems((current) => current.map((candidate) => candidate.id === item.id ? changed : candidate));
      setError("");
    } catch (cause) { setError((cause as Error).message); }
  }
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi");
    if (!needle) return items;
    return items.filter((item) =>
      [item.name, item.component, item.location, item.code].some((value) =>
        (value || "").toLocaleLowerCase("vi").includes(needle),
      ),
    );
  }, [items, query]);
  const groups = groupWorkItems(filtered);
  const completed = items.filter((item) => item.status === "completed").length;
  const pending = items.filter((item) => item.status === "pending_acceptance").length;
  const progress = items.length ? Math.round((completed / items.length) * 100) : 0;
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Điều hành"
        title="Danh mục công việc"
        description="Theo dõi hạng mục theo giai đoạn thi công và cập nhật trạng thái ngay tại hiện trường."
        actions={<span className="app-badge bg-white px-3 py-2 text-sm text-slate-700">{items.length} hạng mục</span>}
      />
      <div className="grid gap-3 sm:grid-cols-3">
        {(
          [
            { label: "Tổng hạng mục", value: items.length, icon: WorkIcon, accent: "#405e9b" },
            { label: "Hoàn thành", value: completed, icon: CheckCircleIcon, accent: "#15803d" },
            { label: "Chờ nghiệm thu", value: pending, icon: ClockIcon, accent: "#b45309" },
          ] satisfies Array<{
            label: string;
            value: number;
            icon: typeof WorkIcon;
            accent: string;
          }>
        ).map(({ label, value, icon: Icon, accent }) => (
          <div key={label} className="app-kpi" style={{ "--kpi-accent": accent } as CSSProperties}>
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
              <Icon className="h-4 w-4 text-slate-400" />
            </div>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-950">{value}</p>
          </div>
        ))}
      </div>
      <div className="app-card app-card-pad">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Tiến độ danh mục</h2>
            <p className="mt-1 text-xs text-slate-500">{completed}/{items.length} hạng mục đã hoàn thành</p>
          </div>
          <span className="text-lg font-semibold tabular-nums text-[#405e9b]">{progress}%</span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} aria-label="Tiến độ công việc">
          <div className="h-full rounded-full bg-[#405e9b]" style={{ width: `${progress}%` }} />
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="app-card app-card-pad">
          <h2 className="text-base font-semibold text-slate-950">Thêm công việc</h2>
          <form onSubmit={createItem} className="mt-3 flex flex-col gap-2 sm:flex-row">
            <input className="app-input" aria-label="Tên công việc" placeholder="Tên công việc mới" value={name} onChange={(event) => setName(event.target.value)} required />
            <button className="app-button app-button-primary shrink-0">Thêm</button>
          </form>
        </section>
        <section className="app-card app-card-pad">
          <h2 className="text-base font-semibold text-slate-950">Nhập từ Excel</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">Đọc sheet DM, xem trước rồi xác nhận nhập.</p>
          <label className="mt-3 block">
            <span className="sr-only">Chọn file Excel danh mục công việc</span>
            <input type="file" accept=".xlsx" className="block w-full text-sm text-slate-600" onChange={(event) => void previewFile(event.target.files?.[0])} />
          </label>
        </section>
      </div>
      {preview.length > 0 && (
        <section className="app-card app-card-pad">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-900">{preview.length} dòng sẽ được nhập</h2>
            <button disabled={saving} onClick={() => void importItems()} className="app-button app-button-primary min-h-10 px-3 disabled:opacity-50">
              {saving ? "Đang nhập..." : "Xác nhận nhập"}
            </button>
          </div>
          <ul className="mt-3 max-h-56 list-disc space-y-1 overflow-y-auto pl-5 text-sm text-slate-700">
            {preview.map((item) => <li key={item.source_row}>{item.name}</li>)}
          </ul>
        </section>
      )}
      {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      <section className="app-card app-card-pad">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-base font-semibold text-slate-950">Hạng mục theo giai đoạn</h2>
          <input className="app-input sm:max-w-xs" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm công việc, cấu kiện..." aria-label="Tìm công việc" />
        </div>
        <div className="mt-4 space-y-3">
          {[...groups].map(([phase, named]) => {
            const phaseItems = [...named.values()].flat();
            const phaseDone = phaseItems.filter((item) => item.status === "completed").length;
            const phaseProgress = phaseItems.length ? Math.round((phaseDone / phaseItems.length) * 100) : 0;
            return (
              <details key={phase} className="rounded-xl border border-slate-200 bg-white">
                <summary className="flex min-h-12 cursor-pointer list-none flex-wrap items-center justify-between gap-2 px-4 py-3 [&::-webkit-details-marker]:hidden">
                  <div>
                    <span className="font-semibold text-slate-900">{phase}</span>
                    <span className="ml-2 text-xs text-slate-500">{named.size} công việc · {phaseItems.length} hạng mục</span>
                  </div>
                  <span className="text-xs font-medium text-slate-500">{phaseProgress}%</span>
                </summary>
                <div className="border-t border-slate-100 px-4 py-3">
                  <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-[#405e9b]" style={{ width: `${phaseProgress}%` }} />
                  </div>
                  <div className="space-y-2">
                    {[...named].map(([key, matching]) => (
                      <div key={key} className="rounded-lg bg-slate-50/70 p-3">
                        <p className="text-sm font-medium text-slate-800">{matching[0].name}</p>
                        <div className="mt-2 grid gap-2">
                          {matching.map((item) => (
                            <label key={item.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                              <span className="min-w-0 text-slate-600">{item.component || item.location || "Chung"}</span>
                              <select aria-label={`Trạng thái ${item.name} ${item.component || item.location || "Chung"}`} className="app-input min-h-10 w-auto py-1.5 text-xs" value={item.status} onChange={(event) => void changeStatus(item, event.target.value)}>
                                {Object.entries(workStatuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                              </select>
                            </label>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </details>
            );
          })}
          {filtered.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">Không có hạng mục phù hợp.</p>}
        </div>
      </section>
    </div>
  );
}

function formatDashboardDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export function Dashboard({
  token,
  projectId,
  date,
  onNavigate,
}: {
  token: string;
  projectId: string;
  date: string;
  onNavigate?: (page: string) => void;
}) {
  const [report, setReport] = useState<{ report_date: string } | null>(null);
  const [summary, setSummary] = useState<ConstructionProgressSummary | null>(null);
  const [summaryFailed, setSummaryFailed] = useState(false);
  const [latestDay, setLatestDay] = useState<LatestDay | null>(null);
  const [latestFailed, setLatestFailed] = useState(false);
  const [segments, setSegments] = useState<SegmentProgress[] | null>(null);
  const [segmentsFailed, setSegmentsFailed] = useState(false);
  const [rows, setRows] = useState<ProgressRow[] | null>(null);
  const [issues, setIssues] = useState<Array<{ type: string; component_id: string }> | null>(null);
  const [issuesFailed, setIssuesFailed] = useState(false);
  const {
    batches,
    loading: batchLoading,
    error: batchError,
  } = useConstructionBatches(projectId);
  const { batchId, setBatchId } = useConstructionBatch(projectId, batches, batchLoading);
  const batchQuery = batchId ? `?batch_id=${encodeURIComponent(batchId)}` : "";
  useEffect(() => {
    const controller = new AbortController();
    setSummaryFailed(false);
    request(`/projects/${projectId}/progress/summary${batchQuery}`, token, { signal: controller.signal }).then(
      (data: ConstructionProgressSummary) => {
        if (!controller.signal.aborted) setSummary(data);
      },
      () => {
        if (!controller.signal.aborted) setSummaryFailed(true);
      },
    );
    return () => controller.abort();
  }, [projectId, token, batchQuery]);
  useEffect(() => {
    const controller = new AbortController();
    setLatestFailed(false);
    setSegmentsFailed(false);
    setIssuesFailed(false);
    Promise.allSettled([
      request(`/projects/${projectId}/overview/latest-day${batchQuery}`, token, { signal: controller.signal }),
      request(`/projects/${projectId}/overview/segments${batchQuery}`, token, { signal: controller.signal }),
      request(`/projects/${projectId}/reconciliation/issues`, token, { signal: controller.signal }),
      listComponentProgress(projectId, undefined, batchId || undefined),
    ]).then(([latest, segment, issuesResult, batchRows]) => {
      if (controller.signal.aborted) return;
      if (latest.status === "fulfilled") setLatestDay(latest.value);
      else setLatestFailed(true);
      if (segment.status === "fulfilled") setSegments(segment.value.segments);
      else setSegmentsFailed(true);
      if (issuesResult.status === "fulfilled") setIssues(issuesResult.value.issues);
      else setIssuesFailed(true);
      if (batchRows.status === "fulfilled") setRows(batchRows.value);
      else setRows(null);
    });
    return () => controller.abort();
  }, [projectId, token, batchQuery, batchId]);
  useEffect(() => {
    let active = true;
    request(`/projects/${projectId}/daily-reports/${date}`, token).then(
      (daily) => {
        if (active) setReport(daily);
      },
      () => {
        if (active) setReport(null);
      },
    );
    return () => { active = false; };
  }, [projectId, token, date]);
  const batchIds = rows ? new Set(rows.map((row) => row.id)) : null;
  const scopedIssues = issues
    ? batchId
      ? batchIds
        ? issues.filter((issue) => batchIds.has(issue.component_id))
        : null
      : issues
    : null;
  const scopedIssueCounts = scopedIssues
    ? scopedIssues.reduce<Record<string, number>>((counts, issue) => {
        counts[issue.type] = (counts[issue.type] ?? 0) + 1;
        return counts;
      }, {})
    : null;
  const acceptedCount = rows
    ? rows.filter(
        (row) => row.acceptance_status === "CONFIRMED" || row.acceptance_status === "APPROVED",
      ).length
    : summary?.acceptance?.confirmed ?? 0;
  const inProgressCount = rows
    ? rows.filter((row) => row.construction_status === "IN_PROGRESS").length
    : summary?.construction.in_progress ?? 0;
  const totalIssues = scopedIssues ? scopedIssues.length : null;
  const cards = [
    ["Đang thi công", rows ? inProgressCount : summary ? summary.construction.in_progress : "—", "Cấu kiện đang thi công", "#b45309"],
    ["Hoàn thành chưa nghiệm thu", scopedIssueCounts ? scopedIssueCounts.WORK_WITHOUT_ACCEPTANCE ?? 0 : "—", "Thi công xong, chưa có BBNT", "#15803d"],
    ["Đã nghiệm thu", rows || summary ? acceptedCount : "—", "BBNT đã xác nhận", "#405e9b"],
    ["Cần xử lý", totalIssues ?? "—", "Từ đối soát dữ liệu", "#b91c1c"],
  ] as const;
  const quickActions = [
    { label: "Cập nhật tiến độ thi công", page: "components", icon: WorkIcon, description: "Ghi tiến độ theo mã cọc, dầm" },
    { label: "Báo cáo hiện trường", page: "daily-report", icon: CameraIcon, description: "Nhân lực, ảnh, nhật ký" },
    { label: "Lập phiếu nghiệm thu", page: "acceptance", icon: AcceptanceIcon, description: "PYC và BBNT" },
    { label: "Hỏi AI", page: "documents", icon: DocumentsIcon, description: "Hỏi đáp về cấu kiện, tiến độ" },
  ];
  return (
    <div className="space-y-6">
      <PageHeader
        title="Tổng quan hôm nay"
        description={`${formatDashboardDate(date)} · Nắm nhanh tiến độ, báo cáo và các việc cần xử lý.`}
      />
      <ConstructionBatchSelector
        batches={batches}
        value={batchId}
        onChange={setBatchId}
        loading={batchLoading}
        error={batchError}
      />
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {cards.map(([label, value, hint, accent]) => (
          <div key={label} className="app-kpi" style={{ "--kpi-accent": accent } as CSSProperties}>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-600">{label}</p>
            <p className="mt-1 text-3xl font-semibold tabular-nums tracking-tight text-slate-950">{value}</p>
            <p className="mt-1 app-text-secondary">{hint}</p>
          </div>
        ))}
      </div>
      {issuesFailed && (
        <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Chưa tải được số đối soát; hai thẻ “Hoàn thành chưa nghiệm thu” và “Cần xử lý” đang tạm trống.
        </p>
      )}
      <section className="app-card app-card-pad">
        <h2 className="text-base font-semibold text-slate-950">Việc nhanh</h2>
        <button
          type="button"
          className="mt-3 flex min-h-14 w-full items-center gap-3 rounded-xl bg-[#405e9b] px-3 py-3 text-left text-white shadow-sm hover:bg-[#344c7e] disabled:opacity-60"
          onClick={() => onNavigate?.("progress-paste")}
          disabled={!onNavigate}
        >
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/15 text-white">
            <WorkIcon className="size-5" />
          </span>
          <span className="min-w-0">
            <span className="block text-base font-semibold">Ghi tiến độ từ tin nhắn</span>
            <span className="block text-sm text-slate-100">Dán tin nhắn Zalo, xem lại rồi ghi</span>
          </span>
        </button>
        <div className="mt-2 grid gap-2 min-[375px]:grid-cols-2 xl:grid-cols-4">
          {quickActions.map(({ page, label, icon: ActionIcon, description }) => (
            <button
              key={page}
              type="button"
              className="flex min-h-14 min-w-0 items-center gap-2 rounded-xl border border-slate-200 bg-white px-2.5 py-2 text-left hover:border-teal-700/40 hover:bg-teal-50 sm:px-3"
              onClick={() => onNavigate?.(page)}
              disabled={!onNavigate}
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-teal-50 text-teal-700">
                <ActionIcon className="size-4" />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-slate-800">{label}</span>
                <span className="block text-xs text-slate-600">{description}</span>
              </span>
            </button>
          ))}
        </div>
      </section>
      <LatestDayCard
        day={latestDay}
        failed={latestFailed}
        today={date}
        todayReportExists={Boolean(report)}
        onOpenTodayReport={onNavigate ? () => onNavigate("daily-report") : undefined}
      />
      <section className="app-card app-card-pad">
        <h2 className="text-base font-semibold text-slate-950">Tiến độ thi công</h2>
        {summaryFailed ? (
          <p role="alert" className="mt-3 text-sm text-red-800">Chưa tải được tiến độ thi công.</p>
        ) : summary ? (
          <ConstructionProgressChart summary={summary} />
        ) : (
          <p role="status" className="mt-3 text-sm text-slate-600">Đang tải tiến độ thi công…</p>
        )}
      </section>
      <section className="app-card app-card-pad">
        <h2 className="text-base font-semibold text-slate-950">Tiến độ theo đoạn</h2>
        {segmentsFailed ? (
          <p role="alert" className="mt-3 text-sm text-red-800">Chưa tải được tiến độ theo đoạn.</p>
        ) : segments ? (
          <SegmentProgressBars segments={segments} />
        ) : (
          <p role="status" className="mt-3 text-sm text-slate-600">Đang tải tiến độ theo đoạn…</p>
        )}
      </section>
    </div>
  );
}
