import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, deletePhoto } from "./api";

const originalFetch = globalThis.fetch;

function fakeResponse(status: number, body?: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => body,
  } as Response;
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe("deletePhoto", () => {
  it("uses the project-scoped /api/v1 route and accepts 204 without a body", async () => {
    const fetchMock = vi.fn(async () => fakeResponse(204));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await expect(deletePhoto("project-1", "photo-1")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/projects/project-1/photos/photo-1");
    expect(init).toMatchObject({ method: "DELETE" });
  });

  it("surfaces 409 for a photo linked to evidence", async () => {
    globalThis.fetch = vi.fn(async () =>
      fakeResponse(409, {
        detail: "Photo is linked to evidence",
        code: "photo_linked",
      }),
    ) as unknown as typeof fetch;

    await expect(deletePhoto("project-1", "photo-1")).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      message: "Photo is linked to evidence",
    } satisfies Partial<ApiError>);
  });
});
