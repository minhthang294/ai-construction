import { useCallback, useEffect, useState } from "react";

export type InstallPromptOutcome = "accepted" | "dismissed" | "unavailable" | "failed";

export type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform?: string }>;
};

export type InstallPromptStore = {
  capture: (event: BeforeInstallPromptEvent) => void;
  hasPrompt: () => boolean;
  clear: () => void;
  prompt: () => Promise<InstallPromptOutcome>;
};

/** The browser prompt is single-use, so use it once and let the next event replace it. */
export function createInstallPromptStore(): InstallPromptStore {
  let deferred: BeforeInstallPromptEvent | null = null;

  return {
    capture(event) {
      event.preventDefault();
      deferred = event;
    },
    hasPrompt: () => deferred !== null,
    clear() {
      deferred = null;
    },
    async prompt() {
      const event = deferred;
      deferred = null;
      if (!event) return "unavailable";
      try {
        await event.prompt();
        return (await event.userChoice).outcome;
      } catch {
        return "failed";
      }
    },
  };
}

export function isStandaloneDisplay(matches: boolean, iosStandalone: boolean | undefined): boolean {
  return matches || iosStandalone === true;
}

export function isIosDevice(userAgent: string): boolean {
  return /iPad|iPhone|iPod/.test(userAgent);
}

export function installInstructions(userAgent: string): string[] {
  if (isIosDevice(userAgent)) {
    return [
      "Mở trang này bằng Safari.",
      "Nhấn nút Chia sẻ.",
      "Chọn “Thêm vào Màn hình chính”.",
      "Bật “Mở dưới dạng ứng dụng web” nếu có, rồi nhấn “Thêm”.",
    ];
  }
  return [
    "Mở menu trình duyệt (⋮ hoặc ⋯).",
    "Chọn “Cài đặt ứng dụng” hoặc “Thêm vào màn hình chính”.",
    "Xác nhận để hoàn tất cài đặt.",
  ];
}

function currentlyStandalone(): boolean {
  if (typeof window === "undefined" || typeof navigator === "undefined") return false;
  return isStandaloneDisplay(
    window.matchMedia ? window.matchMedia("(display-mode: standalone)").matches : false,
    (navigator as Navigator & { standalone?: boolean }).standalone,
  );
}

export function useInstallApp() {
  const [store] = useState(createInstallPromptStore);
  const [installed, setInstalled] = useState(currentlyStandalone);
  const [canPrompt, setCanPrompt] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const handlePrompt = (event: Event) => {
      store.capture(event as BeforeInstallPromptEvent);
      setCanPrompt(true);
    };
    const handleInstalled = () => {
      store.clear();
      setCanPrompt(false);
      setInstalled(true);
    };
    const displayMode = window.matchMedia?.("(display-mode: standalone)");
    const handleDisplayMode = () => setInstalled(currentlyStandalone());

    window.addEventListener("beforeinstallprompt", handlePrompt);
    window.addEventListener("appinstalled", handleInstalled);
    displayMode?.addEventListener?.("change", handleDisplayMode);

    return () => {
      window.removeEventListener("beforeinstallprompt", handlePrompt);
      window.removeEventListener("appinstalled", handleInstalled);
      displayMode?.removeEventListener?.("change", handleDisplayMode);
    };
  }, [store]);

  const promptInstall = useCallback(async () => {
    const outcome = await store.prompt();
    setCanPrompt(store.hasPrompt());
    if (outcome === "accepted") setInstalled(true);
    return outcome;
  }, [store]);

  return { installed, canPrompt, promptInstall };
}

export type InstallAppApi = ReturnType<typeof useInstallApp>;

/** Sidebar install action; instructions replace the unavailable or failed native prompt. */
export default function InstallAppButton({ installed, canPrompt, promptInstall }: InstallAppApi) {
  const [showHelp, setShowHelp] = useState(false);
  const [busy, setBusy] = useState(false);

  if (installed) return null;

  const userAgent = typeof navigator === "undefined" ? "" : navigator.userAgent;
  const steps = installInstructions(userAgent);

  async function handleClick() {
    if (!canPrompt) {
      setShowHelp((open) => !open);
      return;
    }
    setBusy(true);
    const outcome = await promptInstall();
    setBusy(false);
    if (outcome === "failed" || outcome === "unavailable") setShowHelp(true);
  }

  return (
    <div>
      <button
        type="button"
        className="app-nav-item"
        onClick={handleClick}
        disabled={busy}
        aria-expanded={showHelp}
        aria-controls="install-app-instructions"
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
        </svg>
        <span>Cài vào điện thoại</span>
      </button>
      <div
        id="install-app-instructions"
        hidden={!showHelp}
        className="mt-1 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-600"
      >
        <p className="font-semibold text-slate-700">
          {isIosDevice(userAgent) ? "Cài trên iPhone" : "Cài trên Android hoặc trình duyệt khác"}
        </p>
        <ol className="mt-1 list-decimal space-y-1 pl-4">
          {steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </div>
    </div>
  );
}
