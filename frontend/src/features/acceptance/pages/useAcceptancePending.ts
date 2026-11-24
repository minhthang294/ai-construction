import { useEffect, useState } from "react";
import { createRequestFromComponents, listPendingAcceptance } from "../lib/api";
import {
  errorMessage,
  hasPendingFilter,
  pendingFilters,
} from "./acceptancePageModel";
import type {
  AcceptanceNavigationPayload,
  AcceptanceRequest,
  PendingAcceptanceResponse,
} from "../types";

type Options = {
  projectId: string;
  initialState?: AcceptanceNavigationPayload | null;
  refresh: () => Promise<unknown>;
  onCreated: (request: AcceptanceRequest) => void;
  setMessage: (value: string | null) => void;
  setError: (value: string | null) => void;
};

export function useAcceptancePending({
  projectId,
  initialState,
  refresh,
  onCreated,
  setMessage,
  setError,
}: Options) {
  const [pending, setPending] = useState<PendingAcceptanceResponse | null>(null);
  const [pendingSelected, setPendingSelected] = useState<Set<string>>(new Set());
  const [pendingBusy, setPendingBusy] = useState(false);
  const [pendingFilterCleared, setPendingFilterCleared] = useState(false);
  const [pendingTotalAll, setPendingTotalAll] = useState<number | null>(null);
  const pendingFilterAvailable = hasPendingFilter(initialState);
  const pendingFilterActive = pendingFilterAvailable && !pendingFilterCleared;
  const initialComponentKey = (initialState?.component_ids ?? []).join(",");

  async function loadPending(options: { all?: boolean } = {}) {
    const useFilter = pendingFilterActive && !options.all;
    const filters = pendingFilters(initialState, useFilter);
    const [data, all] = await Promise.all([
      listPendingAcceptance(projectId, filters),
      useFilter ? listPendingAcceptance(projectId) : Promise.resolve(null),
    ]);
    setPending(data);
    setPendingTotalAll(all ? all.total_components : data.total_components);
    return data;
  }

  async function clearPendingFilter() {
    setPendingFilterCleared(true);
    setPendingSelected(new Set());
    try {
      await loadPending({ all: true });
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  function togglePending(componentId: string) {
    setPendingSelected((current) => {
      const next = new Set(current);
      if (next.has(componentId)) next.delete(componentId);
      else next.add(componentId);
      return next;
    });
  }

  async function createPendingRequest() {
    if (pendingSelected.size === 0 || pendingBusy) return;
    setPendingBusy(true);
    setError(null);
    try {
      const created = await createRequestFromComponents(projectId, {
        component_ids: [...pendingSelected],
        stage_definition_id: pendingFilterActive
          ? initialState?.stage_definition_id ?? null
          : null,
        event_date: initialState?.event_date ?? null,
      });
      await Promise.all([refresh(), loadPending()]);
      setPendingSelected(new Set());
      onCreated(created);
      setMessage(
        `Đã tạo PYC nháp ${created.number} cho ${pendingSelected.size} cấu kiện. Chưa xác nhận nghiệm thu.`,
      );
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPendingBusy(false);
    }
  }

  useEffect(() => {
    let active = true;
    setPending(null);
    setPendingFilterCleared(false);
    setPendingSelected(new Set(initialState?.component_ids ?? []));
    const filters = pendingFilters(initialState, pendingFilterAvailable);
    Promise.all([
      listPendingAcceptance(projectId, filters),
      pendingFilterAvailable
        ? listPendingAcceptance(projectId)
        : Promise.resolve(null),
    ])
      .then(([data, all]) => {
        if (!active) return;
        setPending(data);
        setPendingTotalAll(all ? all.total_components : data.total_components);
        const pendingIds = new Set(
          data.groups.flatMap((group) =>
            group.components.map((component) => component.component_id),
          ),
        );
        const requested = initialState?.component_ids ?? [];
        if (requested.length) {
          setPendingSelected(
            new Set(requested.filter((componentId) => pendingIds.has(componentId))),
          );
        }
      })
      .catch((cause) => {
        if (active) setError(errorMessage(cause));
      });
    return () => {
      active = false;
    };
    // The navigation payload is read once per project/initial navigation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, initialState?.batch_id, initialState?.stage_definition_id, initialComponentKey]);

  return {
    pending,
    pendingSelected,
    pendingBusy,
    pendingFilterActive,
    pendingTotalAll,
    loadPending,
    clearPendingFilter,
    togglePending,
    createPendingRequest,
  };
}
