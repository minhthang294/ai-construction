import { lazy, Suspense, useEffect, useState } from "react";
import InstallAppButton, { useInstallApp } from "../features/site/components/InstallAppButton";
import { clearDrawingImageCache } from "../features/site/lib/drawingImageCache";
import { Dashboard, ProjectSetup, WorkItemList, request } from "./CorePages";
import type { Project } from "./CorePages";
import ChangePasswordDialog from "./ChangePasswordDialog";
import MenuButton from "../ui/MenuButton";
import { toAcceptanceInitialState, type AcceptanceDraftRequest, type AcceptanceInitialState } from "./acceptanceHandoff";
import {
  AcceptanceIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  CloseIcon,
  ComponentIcon,
  DashboardIcon,
  DocumentsIcon,
  KeyIcon,
  LogoutIcon,
  MenuIcon,
  ProjectIcon,
  SiteIcon,
  WorkIcon,
} from "./AppIcons";

const SiteReportPage = lazy(() => import("../features/site/pages/SiteReportPage"));
const ComponentCatalogImport = lazy(
  () => import("../features/site/components/ComponentCatalogImport"),
);
const AcceptancePage = lazy(
  () => import("../features/acceptance/pages/AcceptancePage"),
);
const EngineeringAIPage = lazy(
  () => import("../features/engineering-ai/pages/EngineeringAIPage"),
);
const ProgressPastePanel = lazy(
  () => import("../features/site/components/ProgressPastePanel"),
);

function PageLoading({ label }: { label: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600"
    >
      Đang tải {label}…
    </div>
  );
}

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

type PageId = "dashboard" | "projects" | "work-items" | "components" | "daily-report" | "acceptance" | "documents" | "progress-paste";

const PAGE_META: Record<PageId, { label: string; description: string }> = {
  dashboard: { label: "Tổng quan", description: "Tình hình công trường hôm nay" },
  projects: { label: "Công trình", description: "Thông tin dùng chung cho báo cáo và nghiệm thu" },
  "work-items": { label: "Công việc", description: "Danh mục và trạng thái hạng mục" },
  components: { label: "Cấu kiện", description: "Danh mục cọc và dầm theo phân đoạn" },
  "daily-report": { label: "Hiện trường", description: "Báo cáo ngày, nhân lực, ảnh và nhật ký" },
  acceptance: { label: "Nghiệm thu", description: "Phiếu yêu cầu và biên bản nghiệm thu" },
  documents: { label: "Hỏi AI", description: "Hỏi đáp về cấu kiện, tiến độ và bản vẽ có dẫn nguồn" },
  "progress-paste": { label: "Ghi tiến độ từ tin nhắn", description: "Dán tin nhắn hiện trường, xem lại rồi ghi" },
};

const NAV_ITEMS: Array<{ id: PageId; icon: typeof DashboardIcon }> = [
  { id: "dashboard", icon: DashboardIcon },
  { id: "components", icon: ComponentIcon },
  { id: "daily-report", icon: SiteIcon },
  { id: "acceptance", icon: AcceptanceIcon },
  { id: "documents", icon: DocumentsIcon },
];

const SETTINGS_ITEMS: Array<{ id: PageId; icon: typeof DashboardIcon }> = [
  { id: "projects", icon: ProjectIcon },
  { id: "work-items", icon: WorkIcon },
];

const MOBILE_NAV: PageId[] = ["dashboard", "components", "daily-report", "acceptance", "documents"];

export default function App() {
  const installApp = useInstallApp();
  const [token, setToken] = useState(localStorage.getItem("access_token") || "");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [page, setPage] = useState<PageId>("dashboard");
  const [pageHistory, setPageHistory] = useState<PageId[]>([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [username, setUsername] = useState(localStorage.getItem("last_username") || "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loginNotice, setLoginNotice] = useState("");
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [acceptanceDirty, setAcceptanceDirty] = useState(false);
  const [reportPrefill, setReportPrefill] = useState<{ date: string; text: string } | null>(null);
  const [journalRequest, setJournalRequest] = useState<{ date: string } | null>(null);
  const [mapViewRequest, setMapViewRequest] = useState(false);
  const [photoPreselect, setPhotoPreselect] = useState<string[] | null>(null);
  const [componentFocus, setComponentFocus] = useState<{ projectId: string; componentId: string } | null>(null);
  const [acceptanceNavigation, setAcceptanceNavigation] = useState<{
    projectId: string;
    state: AcceptanceInitialState;
  } | null>(null);
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
    if (!menuOpen) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  useEffect(() => {
    function openComponent(event: Event) {
      const detail = (event as CustomEvent<{ projectId?: string; recordId?: string }>).detail;
      if (!detail?.recordId) return;
      if (detail.projectId && detail.projectId !== projectId) {
        setProjectId(detail.projectId);
        localStorage.setItem("last_project_id", detail.projectId);
      }
      setPageHistory((current) => [...current, page]);
      setPage("components");
      setComponentFocus({
        projectId: detail.projectId || projectId,
        componentId: detail.recordId,
      });
      setMenuOpen(false);
    }
    window.addEventListener("engineering-ai:open-component", openComponent);
    return () => window.removeEventListener("engineering-ai:open-component", openComponent);
  }, [page, projectId]);

  useEffect(() => {
    if (page !== "acceptance") setAcceptanceNavigation(null);
  }, [page]);

  useEffect(() => {
    if (acceptanceNavigation && acceptanceNavigation.projectId !== projectId) {
      setAcceptanceNavigation(null);
    }
  }, [acceptanceNavigation, projectId]);

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
        void clearDrawingImageCache();
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
      localStorage.setItem("last_username", username);
      await clearDrawingImageCache();
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
    void clearDrawingImageCache();
    setToken("");
    setProjects([]);
    setProjectId("");
    setPage("dashboard");
    setPageHistory([]);
    setShowChangePassword(false);
    setMenuOpen(false);
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
    localStorage.removeItem("access_token");
    void clearDrawingImageCache();
    setToken("");
    setProjects([]);
    setProjectId("");
    setPage("dashboard");
    setPageHistory([]);
    setShowChangePassword(false);
    setMenuOpen(false);
    setError("");
    setLoginNotice("Đổi mật khẩu thành công. Vui lòng đăng nhập lại.");
  }

  function navigate(nextPage: PageId) {
    if (nextPage === page || !canLeaveAcceptance(nextPage)) return;
    setPageHistory((current) => [...current, page]);
    setPage(nextPage);
    setMenuOpen(false);
  }

  function openAcceptanceDraft(request: AcceptanceDraftRequest) {
    if (request.projectId && request.projectId !== projectId) {
      setProjectId(request.projectId);
      localStorage.setItem("last_project_id", request.projectId);
    }
    setAcceptanceNavigation({
      projectId: request.projectId || projectId,
      state: toAcceptanceInitialState(request),
    });
    navigate("acceptance");
  }

  function openDashboardComponent(targetProjectId: string, componentId: string) {
    if (targetProjectId && targetProjectId !== projectId) {
      setProjectId(targetProjectId);
      localStorage.setItem("last_project_id", targetProjectId);
    }
    setPageHistory((current) => [...current, page]);
    setPage("components");
    setComponentFocus({ projectId: targetProjectId, componentId });
  }

  function openFullMap() {
    setMapViewRequest(true);
    navigate("components");
  }

  function goBack() {
    const previous = pageHistory.at(-1) || "dashboard";
    if (!canLeaveAcceptance(previous)) return;
    setPage(previous);
    setPageHistory((current) => current.slice(0, -1));
  }

  if (!token) {
    return (
      <main className="min-h-screen bg-[#0b1220] text-white">
        <div className="grid min-h-screen lg:grid-cols-[1.1fr_.9fr]">
          <section className="relative hidden overflow-hidden border-r border-white/10 p-10 lg:flex lg:flex-col lg:justify-between xl:p-14">
            <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-[#405e9b]/30 blur-3xl" aria-hidden="true" />
            <div className="absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-[#e5322c]/10 blur-3xl" aria-hidden="true" />
            <div className="relative">
              <div className="inline-flex items-center gap-3 rounded-2xl bg-white/95 px-3 py-2 shadow-xl">
                <img src="/sbtech-logo.png" alt="SBTECH" width="54" height="36" className="h-9 w-auto object-contain" />
                <span className="text-sm font-semibold tracking-wide text-slate-900">SBTECH</span>
              </div>
              <h1 className="mt-12 max-w-xl text-4xl font-semibold leading-tight tracking-tight xl:text-5xl">
                Quản lý công trường rõ ràng, ngay tại hiện trường.
              </h1>
              <p className="mt-5 max-w-lg text-base leading-7 text-slate-300">
                Báo cáo ngày, nghiệm thu, hồ sơ kỹ thuật và hỏi đáp AI trong một luồng làm việc thống nhất.
              </p>
              <ul className="mt-8 space-y-3 text-sm text-slate-300">
                {["Báo cáo ngày và nhân lực theo ca", "Phiếu yêu cầu và biên bản nghiệm thu", "Tra cứu bản vẽ, thuyết minh có citation"].map((item) => (
                  <li key={item} className="flex items-center gap-3">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/10 text-white" aria-hidden="true">
                      <CheckCircleIcon className="h-3.5 w-3.5" />
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <p className="relative text-xs text-slate-500">SBTECH · Trợ lý công trường</p>
          </section>

          <section className="flex items-center justify-center p-4 sm:p-8">
            <form onSubmit={login} className="w-full max-w-md space-y-5 rounded-3xl bg-white p-6 text-slate-900 shadow-2xl sm:p-8">
              <div className="lg:hidden">
                <img src="/sbtech-logo.png" alt="SBTECH" width="80" height="54" className="h-11 w-auto object-contain" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#405e9b]">SBTECH · Construction OS</p>
                <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Đăng nhập</h1>
                <p className="mt-2 text-sm leading-6 text-slate-600">Tiếp tục vào không gian làm việc của công trình.</p>
              </div>
              <label className="app-label">
                Tên đăng nhập
                <input
                  className="app-input mt-1.5"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  required
                />
              </label>
              <label className="app-label">
                Mật khẩu
                <input
                  className="app-input mt-1.5"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                />
              </label>
              <button className="app-button app-button-primary w-full">
                Đăng nhập
              </button>
              {loginNotice && (
                <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                  {loginNotice}
                </p>
              )}
              {error && (
                <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                  {error}
                </p>
              )}
            </form>
          </section>
        </div>
      </main>
    );
  }

  const selected = projects.find((project) => project.id === projectId);
  const initials = (username.trim()[0] || "U").toUpperCase();
  const meta = PAGE_META[page];

  return (
    <div className="min-h-screen bg-[#f5f7fb] text-slate-900">
      <a href="#main-content" className="app-skip-link">Bỏ qua điều hướng</a>

      {menuOpen && (
        <button
          type="button"
          aria-label="Đóng menu"
          className="fixed inset-0 z-40 bg-slate-950/45 lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <aside
        id="app-sidebar"
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-slate-200 bg-white shadow-2xl transition-transform duration-200 lg:translate-x-0 lg:shadow-none ${menuOpen ? "translate-x-0" : "-translate-x-full"}`}
        aria-label="Điều hướng chính"
      >
        <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-4">
          <button type="button" className="flex items-center gap-3 text-left" onClick={() => navigate("dashboard")}>
            <img src="/sbtech-logo.png" alt="" width="44" height="30" className="h-8 w-auto object-contain" />
            <span>
              <span className="block text-sm font-semibold tracking-tight text-slate-950">SBTECH</span>
              <span className="block text-[11px] text-slate-500">Trợ lý công trường</span>
            </span>
          </button>
          <button type="button" className="flex h-10 w-10 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 lg:hidden" onClick={() => setMenuOpen(false)} aria-label="Đóng menu">
            <CloseIcon className="h-5 w-5" />
          </button>
        </div>

        <div className="border-b border-slate-200 p-3">
          <p className="px-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Công trình đang làm</p>
          <p className="mt-1 line-clamp-2 px-1 text-sm font-semibold leading-5 text-slate-800">{selected?.name || "Chưa chọn công trình"}</p>
          <p className="mt-0.5 line-clamp-1 px-1 text-xs text-slate-500">{selected?.client || "Chọn ở thanh trên để bắt đầu"}</p>
        </div>

        <nav className="app-scrollbar flex-1 overflow-y-auto p-3">
          <div className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const ItemIcon = item.icon;
              const active = page === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  className="app-nav-item"
                  aria-current={active ? "page" : undefined}
                  onClick={() => navigate(item.id)}
                >
                  <ItemIcon className="h-5 w-5 shrink-0" />
                  <span>{PAGE_META[item.id].label}</span>
                </button>
              );
            })}
          </div>
          <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold text-slate-700">Mẹo sử dụng</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">Bắt đầu từ Tổng quan, sau đó cập nhật hiện trường và nghiệm thu trong ngày.</p>
          </div>
        </nav>

        <div className="border-t border-slate-200 p-3">
          <MenuButton
            className="w-full"
            label={
              <>
                <MenuIcon className="h-5 w-5 shrink-0" />
                <span>Danh mục &amp; cài đặt</span>
                <ChevronDownIcon className="ml-auto h-4 w-4 text-slate-400" />
              </>
            }
            triggerClassName="app-nav-item w-full"
            panelClassName="bottom-full left-0 mb-1 w-full rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl"
          >
            {SETTINGS_ITEMS.map((item) => {
              const ItemIcon = item.icon;
              return (
                <button
                  key={item.id}
                  type="button"
                  className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                  aria-current={page === item.id ? "page" : undefined}
                  onClick={() => navigate(item.id)}
                >
                  <ItemIcon className="h-4 w-4 shrink-0 text-slate-500" />
                  {PAGE_META[item.id].label}
                </button>
              );
            })}
          </MenuButton>
          <InstallAppButton {...installApp} />
          <button
            type="button"
            className="app-nav-item"
            onClick={() => {
              if (canLeaveAcceptance(page)) {
                setShowChangePassword(true);
                setMenuOpen(false);
              }
            }}
          >
            <KeyIcon className="h-5 w-5" /> Đổi mật khẩu
          </button>
          <button type="button" className="app-nav-item text-red-700 hover:bg-red-50 hover:text-red-800" onClick={signOut}>
            <LogoutIcon className="h-5 w-5" /> Đăng xuất
          </button>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
          <div className="mx-auto flex max-w-[96rem] flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2 sm:px-6 sm:py-3">
            <button
              type="button"
              className="flex size-11 shrink-0 items-center justify-center rounded-lg text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 lg:hidden"
              onClick={() => setMenuOpen(true)}
              aria-label="Mở menu"
              aria-expanded={menuOpen}
              aria-controls="app-sidebar"
            >
              <MenuIcon className="h-5 w-5" />
            </button>
            <div className="min-w-0 flex-1">
              <nav aria-label="Đường dẫn" className="flex min-w-0 items-center gap-1 text-xs text-slate-500">
                <span className="hidden sm:inline">SBTECH</span>
                <span className="hidden sm:inline" aria-hidden="true">/</span>
                <span className="truncate font-medium text-slate-700">{meta.label}</span>
              </nav>
              <p className="mt-0.5 hidden text-xs text-slate-500 sm:block">{meta.description}</p>
            </div>
            <label className="order-3 w-full sm:order-none sm:w-auto">
              <span className="sr-only">Chọn công trình</span>
              <select
                value={projectId}
                onChange={(event) => {
                  if (canLeaveAcceptance(page, event.target.value)) {
                    setProjectId(event.target.value);
                    if (event.target.value) localStorage.setItem("last_project_id", event.target.value);
                    setPageHistory([]);
                  }
                }}
                className="app-input min-h-11 max-w-full py-1.5 text-base sm:max-w-[18rem] sm:text-sm"
              >
                <option value="">Chọn công trình</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>{project.name}</option>
                ))}
              </select>
            </label>
            <MenuButton
              className="shrink-0"
              label={
                <>
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#405e9b] text-[11px] font-semibold text-white">{initials}</span>
                  <span className="hidden max-w-24 truncate sm:inline">{username || "Tài khoản"}</span>
                  <ChevronDownIcon className="h-4 w-4 text-slate-400" />
                </>
              }
              triggerClassName="flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-2 py-1.5 text-sm hover:bg-slate-50"
              panelClassName="right-0 z-50 mt-2 w-52 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl"
            >
              {SETTINGS_ITEMS.map((item) => {
                const ItemIcon = item.icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                    aria-current={page === item.id ? "page" : undefined}
                    onClick={() => navigate(item.id)}
                  >
                    <ItemIcon className="h-4 w-4 shrink-0 text-slate-500" />
                    {PAGE_META[item.id].label}
                  </button>
                );
              })}
              <div className="my-1 border-t border-slate-100" aria-hidden="true" />
              <button
                type="button"
                className="block min-h-11 w-full rounded-lg px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                onClick={() => {
                  if (canLeaveAcceptance(page)) setShowChangePassword(true);
                }}
              >
                Đổi mật khẩu
              </button>
              <button type="button" className="block min-h-11 w-full rounded-lg px-3 py-2 text-left text-sm text-red-700 hover:bg-red-50" onClick={signOut}>
                Đăng xuất
              </button>
            </MenuButton>
          </div>
        </header>

        <main id="main-content" className="mx-auto w-full max-w-[96rem] px-4 pb-60 pt-3 sm:px-6 sm:pt-5 lg:pb-10">
          {page !== "dashboard" &&
            page !== "projects" &&
            !NAV_ITEMS.some((item) => item.id === page) && (
            <button type="button" onClick={goBack} className="app-button app-button-ghost mb-3 min-h-11 px-2">
              <ArrowLeftIcon className="h-4 w-4" /> Quay lại
            </button>
          )}
          <Suspense fallback={<PageLoading label={meta.label} />}>
          {page === "projects" ? (
            <ProjectSetup
              token={token}
              projects={projects}
              currentProjectId={projectId}
              onCreated={(project) => {
                setProjects((current) => [project, ...current]);
                setProjectId(project.id);
                localStorage.setItem("last_project_id", project.id);
              }}
              onUpdated={(project) => setProjects((current) => current.map((item) => item.id === project.id ? project : item))}
              onDeleted={(id) => {
                const remaining = projects.filter((project) => project.id !== id);
                setProjects(remaining);
                if (projectId === id) {
                  const next = pickProjectId(remaining, "", localStorage.getItem("last_project_id"));
                  setProjectId(next);
                  if (next) localStorage.setItem("last_project_id", next);
                  else localStorage.removeItem("last_project_id");
                }
              }}
            />
          ) : !projectId ? (
            <section className="app-card app-card-pad mx-auto max-w-2xl text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#405e9b]/10 text-[#405e9b]">
                <ProjectIcon className="h-6 w-6" />
              </div>
              <h1 className="mt-4 text-xl font-semibold text-slate-950">Chọn công trình để bắt đầu</h1>
              <p className="mt-2 text-sm leading-6 text-slate-600">Bạn cần chọn một công trình ở thanh trên hoặc tạo công trình mới.</p>
              <button type="button" className="app-button app-button-primary mt-5" onClick={() => navigate("projects")}>
                Quản lý công trình
              </button>
            </section>
          ) : page === "dashboard" ? (
            <Dashboard
              key={projectId}
              token={token}
              projectId={projectId}
              date={today}
              onNavigate={(next) => navigate(next as PageId)}
              onOpenComponent={openDashboardComponent}
              onOpenAcceptanceDraft={openAcceptanceDraft}
              onOpenMap={openFullMap}
            />
          ) : page === "work-items" ? (
            <WorkItemList token={token} projectId={projectId} />
          ) : page === "progress-paste" ? (
            <ProgressPastePanel
              projectId={projectId}
              onOpenDailyReport={(eventDate, text) => {
                setReportDate(eventDate);
                setReportPrefill({ date: eventDate, text });
                navigate("daily-report");
              }}
              onOpenJournal={(eventDate) => {
                setJournalRequest({ date: eventDate });
                navigate("components");
              }}
              onOpenPhotos={(componentIds) => {
                setPhotoPreselect(componentIds);
                navigate("daily-report");
              }}
              onOpenAcceptance={(request: AcceptanceDraftRequest) => {
                openAcceptanceDraft(request);
              }}
            />
          ) : page === "components" ? (
            <ComponentCatalogImport
              key={projectId}
              projectId={projectId}
              onOpenPaste={() => navigate("progress-paste")}
              initialView={journalRequest ? "journal" : mapViewRequest ? "map" : undefined}
              initialJournalDate={journalRequest?.date}
              onJournalOpened={() => setJournalRequest(null)}
              onViewOpened={() => {
                setJournalRequest(null);
                setMapViewRequest(false);
              }}
              focusComponentId={componentFocus?.componentId}
              onFocusHandled={() => setComponentFocus(null)}
            />
          ) : page === "daily-report" ? (
            <SiteReportPage
              projectId={projectId}
              date={reportDate}
              onDateChange={setReportDate}
              onOpenAcceptance={() => navigate("acceptance")}
              onOpenProgressPaste={() => navigate("progress-paste")}
              prefill={reportPrefill}
              onPrefillConsumed={() => setReportPrefill(null)}
              photoPreselectComponentIds={photoPreselect ?? undefined}
            />
          ) : page === "acceptance" ? (
            <AcceptancePage
              projectId={projectId}
              onDirtyChange={setAcceptanceDirty}
              initialState={
                acceptanceNavigation?.projectId === projectId
                  ? acceptanceNavigation.state
                  : null
              }
            />
          ) : (
            <EngineeringAIPage projectId={projectId} />
          )}
          </Suspense>
        </main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-1.5 shadow-[0_-8px_24px_rgba(15,23,42,0.06)] backdrop-blur lg:hidden" aria-label="Điều hướng nhanh">
        <div className="mx-auto grid max-w-lg grid-cols-5 gap-2">
          {MOBILE_NAV.map((item) => {
            const config = NAV_ITEMS.find((candidate) => candidate.id === item)!;
            const ItemIcon = config.icon;
            const active = page === item;
            return (
              <button
                key={item}
                type="button"
                className={`flex min-h-12 min-w-0 flex-col items-center justify-center gap-0.5 rounded-lg px-0.5 py-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 ${active ? "bg-[#405e9b]/10 text-[#35507f]" : "text-slate-600"}`}
                aria-current={active ? "page" : undefined}
                onClick={() => navigate(item)}
              >
                <ItemIcon className="h-5 w-5" aria-hidden="true" />
                <span className="app-nav-label max-w-full text-balance text-center font-semibold">{PAGE_META[item].label}</span>
              </button>
            );
          })}
        </div>
      </nav>

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
