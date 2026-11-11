import { useEffect, useState } from "react";

export type Project = { id: string; name: string; client?: string; location?: string; report_title?: string };
type WorkItem = { id: string; code: string; name: string; location?: string; component?: string; status: string };
type PreviewItem = Omit<WorkItem, "id" | "status"> & { source_row: number };
const workStatuses = { planned: "Dự kiến", in_progress: "Đang thi công", completed: "Hoàn thành", pending_acceptance: "Chờ nghiệm thu", rectify: "Cần khắc phục" } as const;

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

export function ProjectSetup({ token, projects, onCreated }: { token: string; projects: Project[]; onCreated: (project: Project) => void }) {
  const [name, setName] = useState("");
  const [client, setClient] = useState("");
  const [location, setLocation] = useState("");
  const [reportTitle, setReportTitle] = useState("");
  const [error, setError] = useState("");
  async function create(event: React.FormEvent) {
    event.preventDefault();
    try {
      const project = await request("/projects", token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, client, location, report_title: reportTitle || null }) });
      onCreated(project);
      setName(""); setClient(""); setLocation(""); setReportTitle(""); setError("");
    } catch (cause) { setError((cause as Error).message); }
  }
  return <section className="bg-white rounded-xl p-5 space-y-4">
    <h1 className="text-xl font-semibold">Công trình</h1>
    <ul className="list-disc pl-5">{projects.map((project) => <li key={project.id}>{project.name}</li>)}</ul>
    <form onSubmit={create} className="space-y-3 max-w-lg">
      <h2 className="font-medium">Tạo công trình</h2>
      <input className="w-full border rounded p-2" placeholder="Tên công trình" value={name} onChange={(event) => setName(event.target.value)} required />
      <input className="w-full border rounded p-2" placeholder="Chủ đầu tư" value={client} onChange={(event) => setClient(event.target.value)} />
      <input className="w-full border rounded p-2" placeholder="Địa điểm" value={location} onChange={(event) => setLocation(event.target.value)} />
      <input className="w-full border rounded p-2" placeholder="Tiêu đề báo cáo (tùy chọn)" value={reportTitle} onChange={(event) => setReportTitle(event.target.value)} />
      <button className="bg-teal-700 text-white rounded px-4 py-2">Lưu</button>
    </form>
    {error && <p role="alert" className="text-red-700">{error}</p>}
  </section>;
}

export function WorkItemList({ token, projectId }: { token: string; projectId: string }) {
  const [items, setItems] = useState<WorkItem[]>([]);
  const [preview, setPreview] = useState<PreviewItem[]>([]);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
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
      const item = await request(`/projects/${projectId}/work-items`, token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code, name }) });
      setItems((current) => [...current, item].sort((a, b) => a.code.localeCompare(b.code)));
      setCode(""); setName(""); setError("");
    } catch (cause) { setError((cause as Error).message); }
  }
  async function changeStatus(item: WorkItem, status: string) {
    try {
      const changed = await request(`/projects/${projectId}/work-items/${item.id}`, token, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) });
      setItems((current) => current.map((candidate) => candidate.id === item.id ? changed : candidate));
      setError("");
    } catch (cause) { setError((cause as Error).message); }
  }
  return <section className="bg-white rounded-xl p-5 space-y-4">
    <h1 className="text-xl font-semibold">Danh mục công việc</h1>
    <form onSubmit={createItem} className="grid gap-2 sm:grid-cols-[1fr_2fr_auto]">
      <input className="border rounded p-2" aria-label="Mã công việc" placeholder="Mã công việc" value={code} onChange={(event) => setCode(event.target.value)} required />
      <input className="border rounded p-2" aria-label="Tên công việc" placeholder="Tên công việc" value={name} onChange={(event) => setName(event.target.value)} required />
      <button className="bg-teal-700 text-white rounded px-4 py-2">Thêm công việc</button>
    </form>
    <label className="block">Xem trước danh mục từ sheet DM của Excel<input type="file" accept=".xlsx" className="block mt-2" onChange={(event) => void previewFile(event.target.files?.[0])} /></label>
    {preview.length > 0 && <div><p>{preview.length} dòng sẽ được nhập. Kiểm tra trước khi lưu.</p><ul className="max-h-56 overflow-y-auto list-disc pl-5">{preview.map((item) => <li key={item.source_row}>{item.code}: {item.name}</li>)}</ul><button disabled={saving} onClick={() => void importItems()} className="bg-teal-700 text-white rounded px-4 py-2 mt-2 disabled:opacity-50">Xác nhận nhập</button></div>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <ul className="divide-y">{items.map((item) => <li key={item.id} className="py-2 flex flex-wrap items-center justify-between gap-2"><span><strong>{item.code}</strong> — {item.name}</span><select aria-label={`Trạng thái ${item.code}`} className="border rounded p-2" value={item.status} onChange={(event) => void changeStatus(item, event.target.value)}>{Object.entries(workStatuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></li>)}</ul>
  </section>;
}

export function Dashboard({ token, projectId, date }: { token: string; projectId: string; date: string }) {
  const [items, setItems] = useState<WorkItem[]>([]);
  const [photos, setPhotos] = useState<{ id: string; upload_time: string }[]>([]);
  const [report, setReport] = useState<{ report_date: string; manpower: { count: number | null }[] } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    Promise.allSettled([
      request(`/projects/${projectId}/work-items`, token),
      request(`/projects/${projectId}/photos`, token),
      request(`/projects/${projectId}/daily-reports/${date}`, token),
    ]).then(([work, photo, daily]) => {
      if (!active) return;
      if (work.status === "fulfilled") setItems(work.value);
      else setError(work.reason.message);
      if (photo.status === "fulfilled") setPhotos(photo.value);
      if (daily.status === "fulfilled") setReport(daily.value);
      else setReport(null);
    });
    return () => { active = false; };
  }, [projectId, token, date]);
  const count = (status: string) => items.filter((item) => item.status === status).length;
  const cards = [
    ["Tổng công việc", items.length], ["Đang thi công", count("in_progress")],
    ["Hoàn thành", count("completed")], ["Chờ nghiệm thu", count("pending_acceptance")],
    ["Cần khắc phục", count("rectify")],
  ] as const;
  return <section className="space-y-4">
    <h1 className="text-xl font-semibold">Tổng quan</h1>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">{cards.map(([label, value]) => <div key={label} className="bg-white rounded-xl p-4 shadow-sm"><p className="text-sm text-slate-600">{label}</p><strong className="text-2xl">{value}</strong></div>)}</div>
    <div className="bg-white rounded-xl p-4 space-y-2"><p>Báo cáo ngày {date}: {report ? "Đã ghi" : "Chưa có"}</p><p>Nhân lực đã cập nhật: {report ? report.manpower.reduce((sum, entry) => sum + (entry.count ?? 0), 0) : "Chưa có báo cáo"}</p><p>Ảnh mới nhất: {photos[0]?.upload_time || "Chưa có"}</p></div>
  </section>;
}
