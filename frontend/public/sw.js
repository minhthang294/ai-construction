const CACHE = "site-assistant-shell-v2";
self.addEventListener("install", (event) => event.waitUntil((async () => {
  const cache = await caches.open(CACHE);
  await cache.addAll(["/", "/icon-192.png", "/icon-512.png", "/manifest.webmanifest"]);
  const html = await (await cache.match("/")).text();
  const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^\"]+)"/g)].map((match) => match[1]);
  await cache.addAll(assets);
})()));
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key.startsWith("site-assistant-shell-") && key !== CACHE)
      .map((key) => caches.delete(key))
  )));
});
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  event.respondWith((async () => {
    try {
      const response = await fetch(event.request);
      if (response.ok) {
        try { await (await caches.open(CACHE)).put(event.request, response.clone()); } catch { /* Storage quota cannot block the page. */ }
      }
      return response;
    } catch {
      return (await caches.match(event.request)) || (event.request.mode === "navigate" ? await caches.match("/") : undefined) || Response.error();
    }
  })());
});
