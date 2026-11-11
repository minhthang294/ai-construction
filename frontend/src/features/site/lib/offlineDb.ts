// Minimal IndexedDB helpers for the offline draft + upload queue.
// No external dependency; safe to run in a browser/PWA service-worker context.
import {
  registerQueueFailure,
  type QueueItemStatus,
} from "./queueRetry";
import type { ViewCacheRecord } from "./viewCache";
import { viewCacheKey } from "./viewCache";

const DB_NAME = "site-report-offline";
const DB_VERSION = 2;

export type DraftRecord = {
  key: string; // `${projectId}:${date}`
  projectId: string;
  date: string;
  payload: unknown;
  updatedAt: number;
};

export type ReportQueuePayload = {
  date: string;
  body: unknown;
};

export type PhotoQueuePayload = {
  bytes: ArrayBuffer;
  filename: string;
  type: string;
  reportId?: string | null;
  /** Local report date so a queued photo can find the report after it syncs. */
  reportDate?: string | null;
  category?: string | null;
  location?: string | null;
  component?: string | null;
  stage?: string | null;
};

export type QueueItem = {
  id: string;
  projectId: string;
  kind: "report" | "photo";
  payload: ReportQueuePayload | PhotoQueuePayload;
  createdAt: number;
  /** Number of failed sync attempts, including backoff-pending ones. */
  attempts: number;
  /** Epoch ms before which the next automatic retry must wait. */
  nextRetryAt?: number | null;
  /** `failed` means the attempt budget is exhausted; automatic retry stops. */
  status?: QueueItemStatus | null;
  /** Last error message, kept only for operator visibility. */
  lastError?: string | null;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB is not available in this environment"));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("drafts")) {
        db.createObjectStore("drafts", { keyPath: "key" });
      }
      if (!db.objectStoreNames.contains("queue")) {
        db.createObjectStore("queue", { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains("views")) {
        db.createObjectStore("views", { keyPath: "key" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withStore<T>(
  storeName: "drafts" | "queue" | "views",
  mode: IDBTransactionMode,
  operation: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const db = await openDb();
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(storeName, mode);
      const req = operation(tx.objectStore(storeName));
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
      tx.onerror = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

export async function saveDraft(draft: DraftRecord): Promise<void> {
  await withStore("drafts", "readwrite", (store) => store.put(draft));
}

export async function loadDraft(key: string): Promise<DraftRecord | undefined> {
  return withStore<DraftRecord | undefined>("drafts", "readonly", (store) => store.get(key));
}

export async function deleteDraft(key: string): Promise<void> {
  await withStore("drafts", "readwrite", (store) => store.delete(key));
}

/** Persist the last successfully viewed report + photo metadata (no bytes). */
export async function saveViewCache(
  record: ViewCacheRecord,
): Promise<void> {
  await withStore("views", "readwrite", (store) => store.put(record));
}

export async function loadViewCache(
  projectId: string,
  date: string,
): Promise<ViewCacheRecord | undefined> {
  return withStore<ViewCacheRecord | undefined>("views", "readonly", (store) =>
    store.get(viewCacheKey(projectId, date)),
  );
}

export async function enqueue(item: QueueItem): Promise<void> {
  await withStore("queue", "readwrite", (store) => store.put(item));
}

export async function listQueue(): Promise<QueueItem[]> {
  const items = await withStore<QueueItem[]>("queue", "readonly", (store) => store.getAll());
  return (items ?? []).sort((a, b) => a.createdAt - b.createdAt);
}

/**
 * Queue items are project-scoped.  A sync for one project must never process
 * or delete another project's items, even when they share the same browser
 * profile.
 */
export function filterQueueForProject(
  items: QueueItem[],
  projectId: string,
): QueueItem[] {
  return items.filter((item) => item.projectId === projectId);
}

export async function removeQueue(id: string): Promise<void> {
  await withStore("queue", "readwrite", (store) => store.delete(id));
}

/**
 * Persist one failed attempt with exponential backoff.  Returns the stored
 * item so callers can surface the new status without re-reading IndexedDB.
 */
export async function recordQueueFailure(
  item: QueueItem,
  now: number = Date.now(),
  error?: string | null,
): Promise<QueueItem> {
  const next = registerQueueFailure(item, now, error);
  await enqueue(next);
  return next;
}

/** Stable idempotency key so retries cannot create duplicate records. */
export function reportQueueId(projectId: string, date: string): string {
  return `report:${projectId}:${date}`;
}

export function photoQueueId(): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `photo:${random}`;
}
