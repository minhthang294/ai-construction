import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { describe, expect, it } from "vitest";

describe("PWA shell cache", () => {
  it("keeps fetched app assets available offline and never handles API requests", async () => {
    const listeners: Record<string, (event: any) => void> = {};
    const stored = new Map<string, any>();
    let online = true;
    const cache = {
      addAll: async (paths: string[]) => paths.forEach((path) => stored.set(path, path === "/" ? { text: async () => '<script src="/assets/app.js"></script><link href="/assets/app.css">' } : { path })),
      put: async (request: { url: string }, response: any) => { stored.set(request.url, response); },
      match: async (path: string) => stored.get(path),
    };
    const caches = {
      open: async () => cache,
      keys: async () => [],
      delete: async () => true,
      match: async (request: { url: string } | string) => stored.get(typeof request === "string" ? request : request.url),
    };
    const code = readFileSync(new URL("../public/sw.js", import.meta.url), "utf8");
    runInNewContext(code, {
      self: { location: { origin: "https://site.test" }, addEventListener: (name: string, handler: any) => { listeners[name] = handler; } },
      caches,
      URL,
      Response: { error: () => ({ failed: true }) },
      fetch: async (request: { url: string }) => {
        if (!online) throw new Error("offline");
        return { ok: true, url: request.url, clone() { return this; } };
      },
    });
    let install: Promise<any> | undefined;
    listeners.install({ waitUntil: (value: Promise<any>) => { install = value; } });
    await install;
    expect(stored.has("/assets/app.js") && stored.has("/assets/app.css")).toBe(true);
    const request = { url: "https://site.test/assets/app.js", method: "GET", mode: "same-origin" };
    let response: Promise<any> | undefined;
    const event = { request, respondWith: (value: Promise<any>) => { response = value; } };
    listeners.fetch(event);
    expect((await response)?.url).toBe(request.url);
    online = false;
    listeners.fetch(event);
    expect((await response)?.url).toBe(request.url);
    response = undefined;
    listeners.fetch({ request: { ...request, url: "https://site.test/api/v1/projects" }, respondWith: event.respondWith });
    expect(response).toBeUndefined();
  });
});
