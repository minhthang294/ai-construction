// Pure retry/backoff/discard logic for the offline upload queue.
// Kept free of IndexedDB so it can be unit-tested without a browser.

export const QUEUE_MAX_ATTEMPTS = 8;
export const QUEUE_BASE_BACKOFF_MS = 5_000; // 5 seconds
export const QUEUE_MAX_BACKOFF_MS = 5 * 60_000; // 5 minutes

export type QueueItemStatus = "pending" | "failed";

export type QueueRetryFields = {
  attempts?: number | null;
  nextRetryAt?: number | null;
  status?: QueueItemStatus | null;
  lastError?: string | null;
};

export function normalizeAttempts(value: number | null | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return 0;
  return Math.floor(value);
}

/**
 * Delay before the next attempt.  `attempts` is the number of failures that
 * have already happened: 1 → 5 s, 2 → 10 s, 3 → 20 s … capped at 5 minutes.
 * A fresh item (attempts 0) has no delay.
 */
export function backoffDelayMs(attempts: number): number {
  const failures = normalizeAttempts(attempts);
  if (failures === 0) return 0;
  // Cap the exponent before multiplying to avoid Infinity on bad input.
  const exponent = Math.min(failures - 1, 20);
  return Math.min(QUEUE_MAX_BACKOFF_MS, QUEUE_BASE_BACKOFF_MS * 2 ** exponent);
}

export function isQueueItemFailed(item: QueueRetryFields): boolean {
  return item.status === "failed" || normalizeAttempts(item.attempts) >= QUEUE_MAX_ATTEMPTS;
}

/** True when the item is still pending and its backoff window has elapsed. */
export function isQueueItemDue(item: QueueRetryFields, now: number): boolean {
  if (isQueueItemFailed(item)) return false;
  const next = item.nextRetryAt;
  return typeof next !== "number" || !Number.isFinite(next) || next <= now;
}

/**
 * Record one failed attempt.  Once the attempt budget is exhausted the item is
 * marked `failed` and stops being retried automatically; the user must then
 * discard it explicitly from the offline queue panel.
 */
export function registerQueueFailure<T extends QueueRetryFields>(
  item: T,
  now: number,
  error?: string | null,
): T {
  const attempts = normalizeAttempts(item.attempts) + 1;
  const lastError = error ?? item.lastError ?? null;
  if (attempts >= QUEUE_MAX_ATTEMPTS) {
    return {
      ...item,
      attempts,
      status: "failed",
      nextRetryAt: null,
      lastError,
    };
  }
  return {
    ...item,
    attempts,
    status: "pending",
    nextRetryAt: now + backoffDelayMs(attempts),
    lastError,
  };
}

/**
 * Discard is project-scoped: an item can only be removed from the queue when it
 * belongs to the project currently open on screen.
 */
export function canDiscardQueueItem(
  item: { projectId: string },
  projectId: string,
): boolean {
  return Boolean(projectId) && item.projectId === projectId;
}

/**
 * Return the queue without the selected item.  Untouched items keep their
 * identity and order; the selection is ignored when it belongs to another
 * project or does not exist.
 */
export function discardQueueItem<T extends { id: string; projectId: string }>(
  items: T[],
  id: string,
  projectId: string,
): T[] {
  const target = items.find((item) => item.id === id);
  if (!target || !canDiscardQueueItem(target, projectId)) return items;
  return items.filter((item) => item.id !== id);
}

const STATUS_LABELS: Record<QueueItemStatus, string> = {
  pending: "Chờ đồng bộ",
  failed: "Đồng bộ thất bại",
};

/** Short Vietnamese label for the queue panel. */
export function describeQueueItem(item: QueueRetryFields, now: number): string {
  if (isQueueItemFailed(item)) {
    return `${STATUS_LABELS.failed} sau ${normalizeAttempts(item.attempts)} lần thử`;
  }
  const next = item.nextRetryAt;
  if (typeof next !== "number" || !Number.isFinite(next) || next <= now) {
    return STATUS_LABELS.pending;
  }
  const seconds = Math.max(1, Math.ceil((next - now) / 1000));
  if (seconds < 60) return `${STATUS_LABELS.pending} · thử lại sau ${seconds} giây`;
  return `${STATUS_LABELS.pending} · thử lại sau ${Math.ceil(seconds / 60)} phút`;
}
