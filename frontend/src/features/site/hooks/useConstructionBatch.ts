import { useCallback, useEffect, useState } from "react";
import { listComponentProgress, listConstructionBatches } from "../lib/api";
import type { ConstructionBatch } from "../lib/batches";

const ALL_BATCHES = "__all__";

export function batchStorageKey(projectId: string): string {
  return `construction_batch:${projectId}`;
}

function readRawBatch(projectId: string): string | null {
  try {
    return localStorage.getItem(batchStorageKey(projectId));
  } catch {
    return null;
  }
}

export function readStoredBatch(projectId: string): string {
  const raw = readRawBatch(projectId);
  return raw === null || raw === ALL_BATCHES ? "" : raw;
}

/**
 * Selected construction batch. Without a saved choice, defaults to the batch
 * whose latest non-voided progress event is the most recent; otherwise all.
 * Choosing "all" is stored explicitly so the default does not override it.
 */
export function useConstructionBatch(
  projectId: string,
  batches: ConstructionBatch[] = [],
  loading = false,
) {
  const [batchId, setBatchIdState] = useState(() => readStoredBatch(projectId));

  useEffect(() => {
    setBatchIdState(readStoredBatch(projectId));
  }, [projectId]);

  useEffect(() => {
    if (loading || batches.length === 0) return;
    const raw = readRawBatch(projectId);
    if (raw !== null) {
      if (raw !== ALL_BATCHES && !batches.some((batch) => batch.id === raw)) {
        setBatchIdState("");
        try {
          localStorage.removeItem(batchStorageKey(projectId));
        } catch {
          // Storage can be blocked; the in-memory fallback still applies.
        }
      }
      return;
    }

    let active = true;
    void (async () => {
      const scores = await Promise.all(
        batches.map(async (batch) => {
          try {
            const rows = await listComponentProgress(projectId, undefined, batch.id);
            let latest = "";
            for (const row of rows) {
              const event = row.construction_event;
              if (!event) continue;
              const stamp = `${event.event_date}T${event.created_at}`;
              if (stamp > latest) latest = stamp;
            }
            return { id: batch.id, latest };
          } catch {
            return { id: batch.id, latest: "" };
          }
        }),
      );
      scores.sort((left, right) => right.latest.localeCompare(left.latest));
      if (active && scores[0]?.latest) setBatchIdState(scores[0].id);
    })();
    return () => {
      active = false;
    };
  }, [projectId, batches, loading]);

  const setBatchId = useCallback(
    (value: string) => {
      setBatchIdState(value);
      try {
        localStorage.setItem(batchStorageKey(projectId), value || ALL_BATCHES);
      } catch {
        // Storage can be blocked (private mode); selection still works in memory.
      }
    },
    [projectId],
  );

  return { batchId, setBatchId };
}

export function useConstructionBatches(projectId: string) {
  const [batches, setBatches] = useState<ConstructionBatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setBatches(await listConstructionBatches(projectId));
      setError(null);
    } catch (cause) {
      setBatches([]);
      setError(cause instanceof Error ? cause.message : "Không tải được đợt thi công.");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { batches, loading, error, reload };
}
