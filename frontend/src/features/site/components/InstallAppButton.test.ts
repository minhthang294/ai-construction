import { describe, expect, it } from "vitest";
import {
  createInstallPromptStore,
  installInstructions,
  isIosDevice,
  isStandaloneDisplay,
  type BeforeInstallPromptEvent,
} from "./InstallAppButton";

function fakePromptEvent(outcome: "accepted" | "dismissed" | "throw") {
  let promptCalls = 0;
  let prevented = 0;
  const event = {
    preventDefault: () => {
      prevented += 1;
    },
    prompt: async () => {
      promptCalls += 1;
      if (outcome === "throw") throw new Error("prompt rejected");
    },
    userChoice: Promise.resolve({
      outcome: outcome === "accepted" ? "accepted" : "dismissed",
    }),
  } as unknown as BeforeInstallPromptEvent;
  return { event, promptCalls: () => promptCalls, prevented: () => prevented };
}

describe("install prompt lifecycle", () => {
  it("prevents the browser banner and prompts only when clicked", async () => {
    const fake = fakePromptEvent("accepted");
    const store = createInstallPromptStore();

    store.capture(fake.event);
    expect(fake.prevented()).toBe(1);
    expect(store.hasPrompt()).toBe(true);
    expect(fake.promptCalls()).toBe(0);

    await expect(store.prompt()).resolves.toBe("accepted");
    expect(fake.promptCalls()).toBe(1);
    expect(store.hasPrompt()).toBe(false);

    await expect(store.prompt()).resolves.toBe("unavailable");
    expect(fake.promptCalls()).toBe(1);
  });

  it("keeps a dismissed prompt recoverable for the next event", async () => {
    const store = createInstallPromptStore();
    store.capture(fakePromptEvent("dismissed").event);

    await expect(store.prompt()).resolves.toBe("dismissed");
    expect(store.hasPrompt()).toBe(false);

    const next = fakePromptEvent("accepted");
    store.capture(next.event);
    await expect(store.prompt()).resolves.toBe("accepted");
    expect(next.promptCalls()).toBe(1);
  });

  it("reports a failed prompt and still consumes the event", async () => {
    const fake = fakePromptEvent("throw");
    const store = createInstallPromptStore();
    store.capture(fake.event);

    await expect(store.prompt()).resolves.toBe("failed");
    expect(store.hasPrompt()).toBe(false);
    await expect(store.prompt()).resolves.toBe("unavailable");
  });
});

describe("install instructions", () => {
  const iphone =
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";
  const android =
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36";

  it("uses the Safari share flow on iPhone", () => {
    expect(isIosDevice(iphone)).toBe(true);
    const steps = installInstructions(iphone).join(" ");
    expect(steps).toContain("Chia sẻ");
    expect(steps).toContain("Thêm vào Màn hình chính");
    expect(steps).toContain("Mở dưới dạng ứng dụng web");
  });

  it("uses the browser install menu on Android and other devices", () => {
    expect(isIosDevice(android)).toBe(false);
    const steps = installInstructions(android).join(" ");
    expect(steps).toContain("Cài đặt ứng dụng");
    expect(steps).toContain("Thêm vào màn hình chính");
    expect(steps).not.toContain("Chia sẻ");
  });

  it("detects an installed standalone app", () => {
    expect(isStandaloneDisplay(true, undefined)).toBe(true);
    expect(isStandaloneDisplay(false, true)).toBe(true);
    expect(isStandaloneDisplay(false, undefined)).toBe(false);
  });
});
