import { describe, expect, it } from "vitest";
import {
  backoffDelayMs,
  canDiscardQueueItem,
  describeQueueItem,
  discardQueueItem,
  isQueueItemDue,
  isQueueItemFailed,
  QUEUE_BASE_BACKOFF_MS,
  QUEUE_MAX_ATTEMPTS,
  QUEUE_MAX_BACKOFF_MS,
  registerQueueFailure,
  type QueueItemStatus,
} from "./queueRetry";
import { reportQueueId } from "./offlineDb";

type TestItem = {
  id: string;
  projectId: string;
  attempts: number;
  status?: QueueItemStatus | null;
  nextRetryAt?: number | null;
  lastError?: string | null;
};

function item(
  id: string,
  projectId: string,
  attempts = 0,
  extra: Partial<TestItem> = {},
): TestItem {
  return { id, projectId, attempts, ...extra };
}

describe("offline queue backoff", () => {
  it("grows exponentially from 5 seconds and is capped at 5 minutes", () => {
    expect(backoffDelayMs(0)).toBe(0);
    expect(backoffDelayMs(1)).toBe(5_000);
    expect(backoffDelayMs(2)).toBe(10_000);
    expect(backoffDelayMs(3)).toBe(20_000);
    expect(backoffDelayMs(4)).toBe(40_000);
    expect(backoffDelayMs(5)).toBe(80_000);
    expect(backoffDelayMs(6)).toBe(160_000);
    // 320 s would exceed the ceiling, so it is clamped to 5 minutes.
    expect(backoffDelayMs(7)).toBe(QUEUE_MAX_BACKOFF_MS);
    expect(backoffDelayMs(8)).toBe(QUEUE_MAX_BACKOFF_MS);
    expect(backoffDelayMs(50)).toBe(QUEUE_MAX_BACKOFF_MS);
    expect(QUEUE_BASE_BACKOFF_MS).toBe(5_000);
    expect(QUEUE_MAX_BACKOFF_MS).toBe(300_000);
  });

  it("never decreases as attempts increase", () => {
    let previous = 0;
    for (let attempts = 1; attempts <= 20; attempts += 1) {
      const delay = backoffDelayMs(attempts);
      expect(delay).toBeGreaterThanOrEqual(previous);
      expect(delay).toBeLessThanOrEqual(QUEUE_MAX_BACKOFF_MS);
      previous = delay;
    }
  });

  it("ignores invalid attempt values instead of producing NaN delays", () => {
    expect(backoffDelayMs(-3)).toBe(0);
    expect(backoffDelayMs(Number.NaN)).toBe(0);
    expect(backoffDelayMs(Number.POSITIVE_INFINITY)).toBe(0);
    expect(backoffDelayMs(2.9)).toBe(10_000);
  });
});

describe("offline queue attempt budget", () => {
  it("increments attempts and schedules the next retry with backoff", () => {
    const now = 1_000_000;
    const updated = registerQueueFailure(item("report:p1:2026-11-11", "p1", 2), now);
    expect(updated.attempts).toBe(3);
    expect(updated.status).toBe("pending");
    expect(updated.nextRetryAt).toBe(now + 20_000);
    // Retry keeps the same id, so the server idempotency key is unchanged.
    expect(updated.id).toBe("report:p1:2026-11-11");
  });

  it("stays pending until the max attempt is reached", () => {
    const now = 2_000_000;
    const updated = registerQueueFailure(
      item("photo:a", "p1", QUEUE_MAX_ATTEMPTS - 2),
      now,
    );
    expect(updated.attempts).toBe(QUEUE_MAX_ATTEMPTS - 1);
    expect(updated.status).toBe("pending");
    expect(isQueueItemFailed(updated)).toBe(false);
    expect(updated.nextRetryAt).toBe(now + QUEUE_MAX_BACKOFF_MS);
  });

  it("marks the item failed at max attempts and stops automatic retry", () => {
    const now = 3_000_000;
    const updated = registerQueueFailure(
      item("photo:a", "p1", QUEUE_MAX_ATTEMPTS - 1),
      now,
      "HTTP 500",
    );
    expect(updated.attempts).toBe(QUEUE_MAX_ATTEMPTS);
    expect(updated.status).toBe("failed");
    expect(updated.nextRetryAt).toBeNull();
    expect(updated.lastError).toBe("HTTP 500");
    expect(isQueueItemFailed(updated)).toBe(true);
    expect(isQueueItemDue(updated, now + 10 * 60_000)).toBe(false);
    expect(describeQueueItem(updated, now)).toContain("thất bại");
  });

  it("treats legacy items without backoff fields as due immediately", () => {
    const legacy = { id: "report:p1:2026-11-11", projectId: "p1", attempts: 0 };
    expect(isQueueItemDue(legacy, Date.now())).toBe(true);
  });

  it("waits for nextRetryAt but retries once the window elapses", () => {
    const now = 5_000_000;
    const waiting = item("photo:a", "p1", 1, { nextRetryAt: now + 5_000 });
    expect(isQueueItemDue(waiting, now)).toBe(false);
    expect(isQueueItemDue(waiting, now + 4_999)).toBe(false);
    expect(isQueueItemDue(waiting, now + 5_000)).toBe(true);
  });

  it("describes the remaining wait in seconds and minutes", () => {
    const now = 1_000;
    expect(describeQueueItem(item("a", "p1", 1, { nextRetryAt: now + 3_000 }), now))
      .toBe("Chờ đồng bộ · thử lại sau 3 giây");
    expect(describeQueueItem(item("a", "p1", 6, { nextRetryAt: now + 160_000 }), now))
      .toBe("Chờ đồng bộ · thử lại sau 3 phút");
  });
});

describe("offline queue discard", () => {
  it("removes only the selected item and keeps the original array untouched", () => {
    const queue = [
      item("p1-report", "p1"),
      item("p1-photo", "p1"),
      item("p2-photo", "p2"),
    ];

    const next = discardQueueItem(queue, "p1-photo", "p1");

    expect(next.map((entry) => entry.id)).toEqual(["p1-report", "p2-photo"]);
    expect(queue.map((entry) => entry.id)).toEqual([
      "p1-report",
      "p1-photo",
      "p2-photo",
    ]);
  });

  it("does not allow discarding another project's item", () => {
    const queue = [item("p1-photo", "p1"), item("p2-photo", "p2")];

    expect(canDiscardQueueItem(queue[1], "p1")).toBe(false);
    const next = discardQueueItem(queue, "p2-photo", "p1");

    // Same reference: nothing was removed.
    expect(next).toBe(queue);
    expect(next.map((entry) => entry.id)).toEqual(["p1-photo", "p2-photo"]);
  });

  it("leaves other projects queued when discarding one item of the current project", () => {
    const queue = [
      item("p1-report", "p1"),
      item("p2-report", "p2"),
      item("p2-photo", "p2"),
    ];

    const next = discardQueueItem(queue, "p1-report", "p1");

    expect(next.map((entry) => entry.id)).toEqual(["p2-report", "p2-photo"]);
  });

  it("ignores an unknown id and an empty/missing project id", () => {
    const queue = [item("p1-report", "p1")];
    expect(discardQueueItem(queue, "missing", "p1")).toBe(queue);
    expect(discardQueueItem(queue, "p1-report", "")).toBe(queue);
    expect(canDiscardQueueItem(queue[0], "")).toBe(false);
  });

  it("keeps the report queue id stable so a retry stays idempotent", () => {
    const id = reportQueueId("p1", "2026-11-11");
    const queued = item(id, "p1");
    const failed = registerQueueFailure(queued, 10_000);
    expect(failed.id).toBe(id);
    expect(reportQueueId("p1", "2026-11-11")).toBe(id);
  });
});
