/** Persistent, versioned cache for private drawing sheet images. */

import { ApiError, apiFetch } from "./api";

const CACHE_NAME = "drawing-map-images-v1";
const ACCEPT_HEADER = "image/webp,image/jpeg,*/*";
const memory = new Map<string, Blob>();

function cacheStorage(): CacheStorage | null {
  try {
    return typeof caches === "undefined" ? null : caches;
  } catch {
    return null;
  }
}

/** Normalise the backend path and make it safe as a Cache Storage key. */
export function drawingImageCacheKey(url: string): string {
  const trimmed = url.trim();
  const path = trimmed.startsWith("/api/v1/") ? trimmed.slice(7) : trimmed;
  try {
    const origin =
      typeof location === "undefined" ? "http://localhost" : location.origin;
    return new URL(path, origin).toString();
  } catch {
    return path;
  }
}

export function peekDrawingImageBlob(url: string): Blob | null {
  return memory.get(drawingImageCacheKey(url)) ?? null;
}

export async function readCachedDrawingImage(url: string): Promise<Blob | null> {
  const key = drawingImageCacheKey(url);
  const cached = memory.get(key);
  if (cached) return cached;
  const storage = cacheStorage();
  if (!storage) return null;
  try {
    const cache = await storage.open(CACHE_NAME);
    const response = await cache.match(key);
    if (!response?.ok) return null;
    const blob = await response.blob();
    if (blob.size > 0) memory.set(key, blob);
    return blob.size > 0 ? blob : null;
  } catch {
    return null;
  }
}

async function pruneOldVersions(cache: Cache, key: string): Promise<void> {
  try {
    const requests = await cache.keys();
    await Promise.all(
      requests
        .filter(
          (request) =>
            drawingImageCacheKey(request.url) !== key &&
            new URL(drawingImageCacheKey(request.url)).pathname ===
              new URL(key).pathname,
        )
        .map((request) => cache.delete(request)),
    );
  } catch {
    // Cache pruning is best-effort; quota errors must not block the map.
  }
}

export async function writeCachedDrawingImage(
  url: string,
  blob: Blob,
): Promise<void> {
  const key = drawingImageCacheKey(url);
  try {
    const pathname = new URL(key).pathname;
    for (const existing of memory.keys()) {
      if (existing !== key && new URL(existing).pathname === pathname) {
        memory.delete(existing);
      }
    }
  } catch {
    // Keep the new entry even if an old key cannot be parsed.
  }
  memory.set(key, blob);
  const storage = cacheStorage();
  if (!storage) return;
  try {
    const cache = await storage.open(CACHE_NAME);
    await cache.put(
      key,
      new Response(blob, {
        headers: { "Content-Type": blob.type || "image/jpeg" },
      }),
    );
    await pruneOldVersions(cache, key);
  } catch {
    // Private cache is optional; storage quota cannot break image loading.
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

export async function getDrawingImageBlob(
  url: string,
  signal?: AbortSignal,
  skipCache = false,
): Promise<Blob> {
  if (!skipCache) {
    const cached = await readCachedDrawingImage(url);
    if (cached) return cached;
  }
  const res = await apiFetch(
    url.startsWith("/api/v1/") ? url.slice("/api/v1".length) : url,
    { signal, headers: { Accept: ACCEPT_HEADER } },
  );
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  const blob = await res.blob();
  await writeCachedDrawingImage(url, blob);
  return blob;
}

/** Warm the private cache during idle time; failures stay silent. */
export async function prefetchDrawingSheetImage(url: string): Promise<void> {
  if (peekDrawingImageBlob(url)) return;
  try {
    await getDrawingImageBlob(url);
  } catch {
    // Prefetch is opportunistic.
  }
}

/** Call on logout so one user's private sheets never persist for the next. */
export async function clearDrawingImageCache(): Promise<void> {
  memory.clear();
  const storage = cacheStorage();
  if (!storage) return;
  try {
    await storage.delete(CACHE_NAME);
  } catch {
    // Ignore storage failures during logout.
  }
}
