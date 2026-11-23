import { useCallback, useEffect, useRef, useState } from "react";
import {
  discardQueueItem as discardFromQueue,
  isQueueItemDue,
  isQueueItemFailed,
} from "../lib/queueRetry";
import {
  filterQueueForProject,
  listQueue,
  PhotoQueuePayload,
  recordQueueFailure,
  removeQueue,
  ReportQueuePayload,
} from "../lib/offlineDb";
import type { QueueItem } from "../lib/offlineDb";
import { saveDailyReport, getDailyReport, uploadPhotos } from "../lib/api";
import type { DailyReportInput } from "../types";

function browserOnline(): boolean {
  return typeof navigator === "undefined" ? true : navigator.onLine;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return String(error ?? "Unknown sync error");
}

/**
 * Retry queued report saves and photo uploads when the browser is online.
 * Queue ids double as idempotency keys on the server, so retries cannot create
 * duplicate photos or reports.
 *
 * Failed attempts back off exponentially (5 s → 5 min) and stop automatically
 * after QUEUE_MAX_ATTEMPTS.  A stuck item is only removed when the user
 * explicitly discards it from the queue panel; discarding never touches the
 * report draft or the original photo.
 */
export function useOfflineSync(projectId: string, onChanged?: () => void) {
  const [online, setOnline] = useState<boolean>(browserOnline);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [revision, setRevision] = useState<number>(0);
  const onChangedRef = useRef(onChanged);
  const syncingRef = useRef(false);

  useEffect(() => {
    onChangedRef.current = onChanged;
  }, [onChanged]);

  const refreshQueue = useCallback(async () => {
    const items = filterQueueForProject(await listQueue(), projectId);
    setQueue(items);
    return items;
  }, [projectId]);

  const syncNow = useCallback(async () => {
    if (syncingRef.current) return;
    syncingRef.current = true;
    let changed = false;
    try {
      const items = await refreshQueue();
      if (!browserOnline() || items.length === 0) return;
      setSyncing(true);
      // Reports first: a photo captured before the first save must be able to
      // resolve its report after that report has been created on the server.
      const ordered = [
        ...items.filter((item) => item.kind === "report"),
        ...items.filter((item) => item.kind === "photo"),
      ];
      for (const item of ordered) {
        // Respect the per-item backoff window.  Failed items are never retried
        // automatically; they wait for an explicit discard.
        if (!isQueueItemDue(item, Date.now())) continue;
        try {
          if (item.kind === "report") {
            const payload = item.payload as ReportQueuePayload;
            await saveDailyReport(
              projectId,
              payload.date,
              payload.body as DailyReportInput,
            );
          } else {
            const payload = item.payload as PhotoQueuePayload;
            let reportId = payload.reportId ?? undefined;
            if (!reportId && payload.reportDate) {
              const remote = await getDailyReport(projectId, payload.reportDate);
              if (!remote) {
                // Keep the photo queued until its report can be resolved; this
                // avoids stranding an unlinked photo in a multi-user project.
                throw new Error("Report is not available yet");
              }
              reportId = remote.id;
            }
            const file = new File([payload.bytes], payload.filename, {
              type: payload.type || "application/octet-stream",
            });
            await uploadPhotos(projectId, [file], {
              reportId,
              category: payload.category ?? undefined,
              location: payload.location ?? undefined,
              componentIds: payload.componentIds ?? undefined,
              stage: payload.stage ?? undefined,
              workItemIds: payload.workItemIds?.length
                ? payload.workItemIds
                : undefined,
              clientUploadIds: [item.id],
            });
          }
          await removeQueue(item.id);
          changed = true;
        } catch (error) {
          await recordQueueFailure(item, Date.now(), errorMessage(error));
        }
      }
      await refreshQueue();
      if (changed) {
        setRevision((value) => value + 1);
        onChangedRef.current?.();
      }
    } finally {
      syncingRef.current = false;
      setSyncing(false);
    }
  }, [projectId, refreshQueue]);

  /**
   * Remove one selected queue item.  Project-scoped: returns false without
   * touching IndexedDB when the item belongs to another project (or is gone).
   */
  const discard = useCallback(
    async (id: string): Promise<boolean> => {
      try {
        const items = filterQueueForProject(await listQueue(), projectId);
        const next = discardFromQueue(items, id, projectId);
        if (next.length === items.length) return false;
        await removeQueue(id);
        setQueue(next);
        return true;
      } catch {
        return false;
      }
    },
    [projectId],
  );

  useEffect(() => {
    const handleOnline = () => {
      setOnline(true);
      void syncNow();
    };
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [syncNow]);

  useEffect(() => {
    void syncNow();
    // Refresh the queue (and retry due items) every 15 s.  Offline this only
    // updates the pending counter; no network request is made.
    const timer = window.setInterval(() => {
      void syncNow();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [syncNow]);

  const pending = queue.filter((item) => !isQueueItemFailed(item)).length;
  const failed = queue.length - pending;

  return {
    online,
    pending,
    failed,
    queue,
    syncing,
    revision,
    syncNow,
    discard,
  };
}
