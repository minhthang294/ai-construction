import { useEffect, useState } from "react";
import { SiteReportPage } from "../features/site";
import { AcceptancePage } from "../features/acceptance";
import { EngineeringAIPage } from "../features/engineering-ai";
import { Dashboard, ProjectSetup, WorkItemList, request } from "./CorePages";
import type { Project } from "./CorePages";


export default function App() {
  const [token, setToken] = useState(localStorage.getItem("access_token") || "");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [page, setPage] = useState("dashboard");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const today = `${parts.find((part) => part.type === "year")?.value}-${parts.find((part) => part.type === "month")?.value}-${parts.find((part) => part.type === "day")?.value}`;
  const [reportDate, setReportDate] = useState(today);

  useEffect(() => {
    if (!token) return;
    request("/projects", token).then(setProjects).catch((e) => { setError(e.message); setToken(""); localStorage.removeItem("access_token"); });
  }, [token]);

  async function login(event: React.FormEvent) {
    event.preventDefault();
    try {
      const result = await request("/auth/login", "", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
      localStorage.setItem("access_token", result.access_token);
      setToken(result.access_token);
      setPassword("");
      setError("");
    } catch (e) { setError((e as Error).message); }
  }

  if (!token) return <main className="min-h-screen bg-slate-50 flex items-center justify-center p-4"><form onSubmit={login} className="w-full max-w-sm bg-white p-6 rounded-xl shadow space-y-4"><h1 className="text-2xl font-semibold">Trợ lý công trường</h1><label className="block">Tên đăng nhập<input className="mt-1 w-full border rounded p-3" value={username} onChange={(e) => setUsername(e.target.value)} required /></label><label className="block">Mật khẩu<input type="password" className="mt-1 w-full border rounded p-3" value={password} onChange={(e) => setPassword(e.target.value)} required /></label><button className="w-full bg-teal-700 text-white rounded p-3">Đăng nhập</button>{error && <p role="alert" className="text-red-700">{error}</p>}</form></main>;

  const selected = projects.find((project) => project.id === projectId);
  const menu = ["dashboard", "projects", "work-items", "daily-report", "manpower", "photos", "acceptance", "documents", "ai", "history"];
  const labels: Record<string, string> = { dashboard: "Tổng quan", projects: "Công trình", "work-items": "Công việc", "daily-report": "Báo cáo ngày", manpower: "Nhân lực", photos: "Ảnh hiện trường", acceptance: "Nghiệm thu", documents: "Kho tài liệu", ai: "AI Assistant", history: "Lịch sử" };
  return <div className="min-h-screen bg-slate-50 text-slate-900"><header className="bg-teal-800 text-white p-4"><div className="max-w-5xl mx-auto flex justify-between items-center"><strong>Trợ lý công trường</strong><button onClick={() => { void request("/auth/logout", token, { method: "POST" }).catch(() => undefined); localStorage.removeItem("access_token"); setToken(""); }} className="text-sm underline">Đăng xuất</button></div></header><div className="max-w-5xl mx-auto p-3"><label className="block mb-3">Công trình<select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="block w-full p-2 rounded border"><option value="">Chọn công trình</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label><nav className="flex gap-2 overflow-x-auto pb-3" aria-label="Điều hướng chính">{menu.map((item) => <button key={item} onClick={() => setPage(item)} className={`whitespace-nowrap rounded px-3 py-2 ${page === item ? "bg-teal-700 text-white" : "bg-white border"}`}>{labels[item]}</button>)}</nav>{page === "projects" ? <ProjectSetup token={token} projects={projects} onCreated={(project) => { setProjects((current) => [project, ...current]); setProjectId(project.id); }} /> : projectId && page === "dashboard" ? <Dashboard token={token} projectId={projectId} date={today} /> : projectId && page === "work-items" ? <WorkItemList token={token} projectId={projectId} /> : projectId && ["daily-report", "manpower", "photos", "history"].includes(page) ? <SiteReportPage projectId={projectId} date={reportDate} onDateChange={setReportDate} onOpenAcceptance={() => setPage("acceptance")} /> : projectId && page === "acceptance" ? <AcceptancePage projectId={projectId} /> : projectId && (page === "documents" || page === "ai") ? <EngineeringAIPage projectId={projectId} /> : <section className="bg-white rounded-xl p-5 shadow-sm"><h1 className="text-xl font-semibold">{labels[page]}</h1>{selected ? <p className="mt-2">{selected.name}</p> : <p className="mt-2">Chọn công trình để tiếp tục.</p>}</section>}</div></div>;
}
