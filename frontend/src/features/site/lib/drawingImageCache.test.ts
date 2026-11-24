import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearDrawingImageCache,
  drawingImageCacheKey,
  getDrawingImageBlob,
  peekDrawingImageBlob,
  readCachedDrawingImage,
  writeCachedDrawingImage,
} from "./drawingImageCache";

class MemoryCache {
  private store = new Map<string, Response>();

  async match(key: string): Promise<Response | undefined> {
    return this.store.get(key)?.clone();
  }

  async put(key: string, response: Response): Promise<void> {
    this.store.set(key, response.clone());
  }

  async keys(): Promise<Request[]> {
    return [...this.store.keys()].map((key) => new Request(key));
  }

  async delete(key: string | Request): Promise<boolean> {
    const value = typeof key === "string" ? key : key.url;
    return this.store.delete(value);
  }
}

const stores = new Map<string, MemoryCache>();
const fakeCaches = {
  async open(name: string) {
    let cache = stores.get(name);
    if (!cache) {
      cache = new MemoryCache();
      stores.set(name, cache);
    }
    return cache;
  },
  async delete(name: string) {
    return stores.delete(name);
  },
  async keys() {
    return [...stores.keys()];
  },
} as unknown as CacheStorage;

const IMAGE = "/projects/p1/drawing-map/pd2-beam/image?v=abc123";

describe("drawing image cache", () => {
  beforeEach(async () => {
    stores.clear();
    vi.stubGlobal("caches", fakeCaches);
    await clearDrawingImageCache();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("normalises api-relative keys and keeps the version query", () => {
    expect(drawingImageCacheKey(`/api/v1${IMAGE}`)).toBe(
      `http://localhost${IMAGE}`,
    );
    expect(drawingImageCacheKey(IMAGE)).toBe(`http://localhost${IMAGE}`);
  });

  it("writes and reads the same blob from memory and Cache Storage", async () => {
    const blob = new Blob(["sheet-bytes"], { type: "image/webp" });
    await writeCachedDrawingImage(IMAGE, blob);

    expect(peekDrawingImageBlob(IMAGE)).toBe(blob);
    const cached = await readCachedDrawingImage(IMAGE);
    expect(cached).not.toBeNull();
    expect(await cached!.text()).toBe("sheet-bytes");
  });

  it("keeps only the newest version of one sheet path", async () => {
    await writeCachedDrawingImage(`${IMAGE}`, new Blob(["v1"]));
    await writeCachedDrawingImage(
      "/projects/p1/drawing-map/pd2-beam/image?v=def456",
      new Blob(["v2"]),
    );

    expect(peekDrawingImageBlob(IMAGE)).toBeNull();
    const newest = await readCachedDrawingImage(
      "/projects/p1/drawing-map/pd2-beam/image?v=def456",
    );
    expect(await newest!.text()).toBe("v2");
  });

  it("skips the network when the versioned blob is already cached", async () => {
    const response = new Response(new Blob(["network-image"]), { status: 200 });
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal("fetch", fetchMock);

    const first = await getDrawingImageBlob(IMAGE);
    const second = await getDrawingImageBlob(IMAGE);

    expect(await first.text()).toBe("network-image");
    expect(await second.text()).toBe("network-image");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("clears memory and the named cache on logout", async () => {
    await writeCachedDrawingImage(IMAGE, new Blob(["private"]));
    await clearDrawingImageCache();

    expect(peekDrawingImageBlob(IMAGE)).toBeNull();
    expect(await readCachedDrawingImage(IMAGE)).toBeNull();
    const cache = await fakeCaches.open("drawing-map-images-v1");
    expect(await cache.keys()).toEqual([]);
  });
});
