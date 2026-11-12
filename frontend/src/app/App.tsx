import { useEffect, useState } from "react";
import { SiteReportPage } from "../features/site";
import { AcceptancePage } from "../features/acceptance";
import { EngineeringAIPage } from "../features/engineering-ai";
import { Dashboard, ProjectSetup, WorkItemList, request } from "./CorePages";
import type { Project } from "./CorePages";
import ChangePasswordDialog from "./ChangePasswordDialog";

export function needsAcceptanceLeaveConfirmation(
  page: string,
  nextPage: string,
  projectId: string,
  nextProjectId: string,
  dirty: boolean,
) {
  return page === "acceptance" && dirty && (nextPage !== page || nextProjectId !== projectId);
}

export function pickProjectId(projects: Project[], current: string, recent: string | null) {
  return projects.find((project) => project.id === current)?.id ||
    projects.find((project) => project.id === recent)?.id || projects[0]?.id || "";
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("access_token") || "");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [page, setPage] = useState("dashboard");
  const [pageHistory, setPageHistory] = useState<string[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loginNotice, setLoginNotice] = useState("");
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [acceptanceDirty, setAcceptanceDirty] = useState(false);
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
      .then((loaded: Project[]) => {
        setProjects(loaded);
        setProjectId((current) => pickProjectId(loaded, current, localStorage.getItem("last_project_id")));
      })
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
    if (!canLeaveAcceptance("dashboard")) return;
    void request("/auth/logout", token, { method: "POST" }).catch(() => undefined);
    localStorage.removeItem("access_token");
    setToken("");
    setProjects([]);
    setProjectId("");
    setPage("dashboard");
    setPageHistory([]);
    setShowChangePassword(false);
    setLoginNotice("");
    setError("");
  }

  function canLeaveAcceptance(nextPage: string, nextProjectId = projectId) {
    return (
      !needsAcceptanceLeaveConfirmation(page, nextPage, projectId, nextProjectId, acceptanceDirty) ||
      window.confirm("PYC/BBNT có thay đổi chưa lưu. Bỏ thay đổi và tiếp tục?")
    );
  }

  function handlePasswordChanged() {
    // The backend revokes the token after a successful password change.
    localStorage.removeItem("access_token");
    setToken("");
    setProjects([]);
    setProjectId("");
    setPage("dashboard");
    setPageHistory([]);
    setShowChangePassword(false);
    setError("");
    setLoginNotice("Đổi mật khẩu thành công. Vui lòng đăng nhập lại.");
  }

  function navigate(nextPage: string) {
    if (nextPage === page || !canLeaveAcceptance(nextPage)) return;
    setPageHistory((current) => [...current, page]);
    setPage(nextPage);
  }

  function goBack() {
    const previous = pageHistory.at(-1) || "dashboard";
    if (!canLeaveAcceptance(previous)) return;
    setPage(previous);
    setPageHistory((current) => current.slice(0, -1));
  }

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <form
          onSubmit={login}
          className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 shadow"
        >
          <img src="/sbtech-logo.png" alt="SBTECH" width="90" height="60" className="h-12 w-auto object-contain" />
          <h1 className="text-2xl font-semibold text-teal-900">Trợ lý công trường</h1>
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
    "acceptance",
    "documents",
  ];
  const labels: Record<string, string> = {
    dashboard: "Tổng quan",
    projects: "Công trình",
    "work-items": "Công việc",
    "daily-report": "Hiện trường",
    acceptance: "Nghiệm thu",
    documents: "Hồ sơ & AI",
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b-4 border-red-600 bg-teal-800 p-3 text-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2"><img src="/sbtech-logo.png" alt="SBTECH" width="60" height="40" className="h-10 w-auto rounded bg-white object-contain" /><strong>Trợ lý công trường</strong></div>
          <div className="flex items-center gap-3 text-sm">
            <button
              type="button"
              className="underline"
              onClick={() => {
                if (canLeaveAcceptance("dashboard")) setShowChangePassword(true);
              }}
            >
              Đổi mật khẩu
            </button>
            <button type="button" className="underline" onClick={signOut}>
              Đăng xuất
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-5xl p-3 sm:p-5">
        <label className="mb-3 block">
          Công trình
          <select
            value={projectId}
            onChange={(event) => {
              if (canLeaveAcceptance(page, event.target.value)) {
                setProjectId(event.target.value);
                if (event.target.value) localStorage.setItem("last_project_id", event.target.value);
                setPageHistory([]);
              }
            }}
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

        <div className="mb-3 flex min-h-11 items-center gap-2 text-sm">
          {page !== "dashboard" && <button type="button" onClick={goBack} className="min-h-11 rounded-lg border bg-white px-3 font-medium text-teal-900">← Quay lại</button>}
          <nav aria-label="Đường dẫn" className="flex min-w-0 flex-wrap items-center gap-1 text-slate-600">
            <button type="button" onClick={() => navigate("dashboard")} className="min-h-11 px-2 underline">{selected?.name || "Công trình"}</button>
            {page !== "dashboard" && <><span aria-hidden="true">/</span><span aria-current="page" className="font-semibold text-slate-900">{labels[page]}</span></>}
          </nav>
        </div>

        <nav
          className="grid grid-cols-3 gap-2 pb-3 sm:flex sm:flex-wrap"
          aria-label="Điều hướng chính"
        >
          {menu.map((item) => (
            <button
              key={item}
              onClick={() => {
                navigate(item);
              }}
              aria-current={page === item ? "page" : undefined}
              className={`min-h-11 rounded px-2 py-2 text-sm sm:px-3 ${
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
              localStorage.setItem("last_project_id", project.id);
            }}
            onUpdated={(project) => setProjects((current) => current.map((item) => item.id === project.id ? project : item))}
          />
        ) : projectId && page === "dashboard" ? (
          <Dashboard token={token} projectId={projectId} date={today} />
        ) : projectId && page === "work-items" ? (
          <WorkItemList token={token} projectId={projectId} />
        ) : projectId && page === "daily-report" ? (
          <SiteReportPage
            projectId={projectId}
            date={reportDate}
            onDateChange={setReportDate}
            onOpenAcceptance={() => navigate("acceptance")}
          />
        ) : projectId && page === "acceptance" ? (
          <AcceptancePage projectId={projectId} onDirtyChange={setAcceptanceDirty} />
        ) : projectId && page === "documents" ? (
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
