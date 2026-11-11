import { describe, expect, it } from "vitest";
import {
  filterQueueForProject,
  photoQueueId,
  reportQueueId,
  type QueueItem,
} from "./offlineDb";

function queueItem(
  id: string,
  projectId: string,
  kind: "report" | "photo",
  createdAt: number,
): QueueItem {
  return {
    id,
    projectId,
    kind,
    payload:
      kind === "report"
        ? { date: "2026-11-11", body: {} }
        : {
            bytes: new ArrayBuffer(1),
            filename: "a.jpg",
            type: "image/jpeg",
          },
    createdAt,
    attempts: 0,
  };
}

describe("offline queue ids", () => {
  it("uses a stable report id per project and date", () => {
    expect(reportQueueId("p1", "2026-11-11")).toBe("report:p1:2026-11-11");
    expect(reportQueueId("p1", "2026-11-11")).toBe(
      reportQueueId("p1", "2026-11-11"),
    );
    expect(reportQueueId("p1", "2026-11-11")).not.toBe(
      reportQueueId("p1", "2026-11-12"),
    );
  });

  it("creates unique photo idempotency keys", () => {
    const first = photoQueueId();
    const second = photoQueueId();
    expect(first).toMatch(/^photo:/);
    expect(first).not.toBe(second);
  });
});

describe("offline queue project isolation", () => {
  it("filters replay to the current project and leaves other projects queued", () => {
    const queue = [
      queueItem("p1-report", "p1", "report", 1),
      queueItem("p2-report", "p2", "report", 2),
      queueItem("p1-photo", "p1", "photo", 3),
    ];

    expect(filterQueueForProject(queue, "p1").map((item) => item.id)).toEqual([
      "p1-report",
      "p1-photo",
    ]);
    expect(filterQueueForProject(queue, "p2").map((item) => item.id)).toEqual([
      "p2-report",
    ]);
    expect(filterQueueForProject(queue, "p3")).toEqual([]);
    // The original queue still contains the other project's item.
    expect(queue.map((item) => item.id)).toEqual([
      "p1-report",
      "p2-report",
      "p1-photo",
    ]);
  });
});
