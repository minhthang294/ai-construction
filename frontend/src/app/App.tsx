import { useEffect, useState } from "react";
import { SiteReportPage } from "../features/site";
import { AcceptancePage } from "../features/acceptance";
import { EngineeringAIPage } from "../features/engineering-ai";
import { Dashboard, ProjectSetup, WorkItemList, request } from "./CorePages";
import type { Project } from "./CorePages";
import ChangePasswordDialog from "./ChangePasswordDialog";

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("access_token") || "");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [page, setPage] = useState("dashboard");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loginNotice, setLoginNotice] = useState("");
  const [showChangePassword, setShowChangePassword] = useState(false);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const today = `${parts.find((part) => part.type === "year")?.value}-${
    parts.find((part) => part.type === "month")?.value
  }-${parts.find((part) => part.type === "day")?.value}`;
  const [reportDate, setReportDate] = useState(today);

  useEffect(() => {
    if (!token) return;
    request("/projects", token)
      .then(setProjects)
      .catch((cause) => {
        setError(cause.message);
        setToken("");
        localStorage.removeItem("access_token");
      });
  }, [token]);

  async function login(event: React.FormEvent) {
    event.preventDefault();
    try {
      const result = await request("/auth/login", "", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      localStorage.setItem("access_token", result.access_token);
      setToken(result.access_token);
      setPassword("");
      setError("");
      setLoginNotice("");
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  function signOut() {
    void request("/auth/logout", token, { method: "POST" }).catch(() => undefined);
    localStorage.removeItem("access_token");
    setToken("");
    setProjects([]);
    setProjectId("");
    setPage("dashboard");
    setShowChangePassword(false);
    setLoginNotice("");
    setError("");
  }

  function handlePasswordChanged() {
    // The backend revokes the token after a successful password change.
    localStorage.removeItem("access_token");
    setToken("");
    setProjects([]);
    setProjectId("");
    setPage("dashboard");
    setShowChangePassword(false);
    setError("");
    setLoginNotice("Đổi mật khẩu thành công. Vui lòng đăng nhập lại.");
  }

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <form
          onSubmit={login}
          className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 shadow"
        >
          <h1 className="text-2xl font-semibold">Trợ lý công trường</h1>
          <label className="block">
            Tên đăng nhập
            <input
              className="mt-1 w-full rounded border p-3"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </label>
          <label className="block">
            Mật khẩu
            <input
              type="password"
              className="mt-1 w-full rounded border p-3"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <button className="w-full rounded bg-teal-700 p-3 text-white">
            Đăng nhập
          </button>
          {loginNotice && (
            <p role="status" className="rounded bg-green-50 p-2 text-green-800">
              {loginNotice}
            </p>
          )}
          {error && (
            <p role="alert" className="text-red-700">
              {error}
            </p>
          )}
        </form>
      </main>
    );
  }

  const selected = projects.find((project) => project.id === projectId);
  const menu = [
    "dashboard",
    "projects",
    "work-items",
    "daily-report",
    "manpower",
    "photos",
    "acceptance",
    "documents",
    "ai",
    "history",
  ];
  const labels: Record<string, string> = {
    dashboard: "Tổng quan",
    projects: "Công trình",
    "work-items": "Công việc",
    "daily-report": "Báo cáo ngày",
    manpower: "Nhân lực",
    photos: "Ảnh hiện trường",
    acceptance: "Nghiệm thu",
    documents: "Kho tài liệu",
    ai: "AI Assistant",
    history: "Lịch sử",
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="bg-teal-800 p-4 text-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2">
          <strong>Trợ lý công trường</strong>
          <div className="flex items-center gap-3 text-sm">
            <button
              type="button"
              className="underline"
              onClick={() => setShowChangePassword(true)}
            >
              Đổi mật khẩu
            </button>
            <button type="button" className="underline" onClick={signOut}>
              Đăng xuất
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-5xl p-3">
        <label className="mb-3 block">
          Công trình
          <select
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            className="block w-full rounded border p-2"
          >
            <option value="">Chọn công trình</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>

        <nav
          className="flex gap-2 overflow-x-auto pb-3"
          aria-label="Điều hướng chính"
        >
          {menu.map((item) => (
            <button
              key={item}
              onClick={() => setPage(item)}
              className={`whitespace-nowrap rounded px-3 py-2 ${
                page === item ? "bg-teal-700 text-white" : "border bg-white"
              }`}
            >
              {labels[item]}
            </button>
          ))}
        </nav>

        {page === "projects" ? (
          <ProjectSetup
            token={token}
            projects={projects}
            onCreated={(project) => {
              setProjects((current) => [project, ...current]);
              setProjectId(project.id);
            }}
          />
        ) : projectId && page === "dashboard" ? (
          <Dashboard token={token} projectId={projectId} date={today} />
        ) : projectId && page === "work-items" ? (
          <WorkItemList token={token} projectId={projectId} />
        ) : projectId &&
          ["daily-report", "manpower", "photos", "history"].includes(page) ? (
          <SiteReportPage
            projectId={projectId}
            date={reportDate}
            onDateChange={setReportDate}
            onOpenAcceptance={() => setPage("acceptance")}
          />
        ) : projectId && page === "acceptance" ? (
          <AcceptancePage projectId={projectId} />
        ) : projectId && (page === "documents" || page === "ai") ? (
          <EngineeringAIPage projectId={projectId} />
        ) : (
          <section className="rounded-xl bg-white p-5 shadow-sm">
            <h1 className="text-xl font-semibold">{labels[page]}</h1>
            {selected ? (
              <p className="mt-2">{selected.name}</p>
            ) : (
              <p className="mt-2">Chọn công trình để tiếp tục.</p>
            )}
          </section>
        )}
      </div>

      {showChangePassword && (
        <ChangePasswordDialog
          token={token}
          onClose={() => setShowChangePassword(false)}
          onSuccess={handlePasswordChanged}
        />
      )}
    </div>
  );
}
