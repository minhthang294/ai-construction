import { useCallback, useEffect, useState } from "react";
import { listConstructionBatches } from "../lib/api";
import type { ConstructionBatch } from "../lib/batches";

export function batchStorageKey(projectId: string): string {
  return `construction_batch:${projectId}`;
}

export function readStoredBatch(projectId: string): string {
  try {
    return localStorage.getItem(batchStorageKey(projectId)) || "";
  } catch {
    return "";
  }
}

export function useConstructionBatch(projectId: string) {
  const [batchId, setBatchIdState] = useState(() => readStoredBatch(projectId));

  useEffect(() => {
    setBatchIdState(readStoredBatch(projectId));
  }, [projectId]);

  const setBatchId = useCallback(
    (value: string) => {
      setBatchIdState(value);
      try {
        if (value) localStorage.setItem(batchStorageKey(projectId), value);
        else localStorage.removeItem(batchStorageKey(projectId));
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
