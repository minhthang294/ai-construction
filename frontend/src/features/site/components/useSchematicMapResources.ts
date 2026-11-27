/** Progress rows -> generated schematic sheets; no drawing image is loaded. */

import { useCallback, useEffect, useMemo, useState } from "react";
import { listComponentProgress } from "../lib/api";
import {
  EMPTY_DRAWING_FILTERS,
  countMarkers,
  filterDrawingSheets,
  pickPrimarySheet,
  type DrawingFilters,
  type DrawingMap,
  type DrawingMarker,
  type DrawingSheet,
  type ImageBox,
} from "../lib/drawingMap";
import {
  fetchMainWorks,
  mainWorkForDefinition,
  type MainWork,
} from "../lib/mainWorks";
import type { ProgressRow } from "../lib/componentProgress";
import { buildSchematicPlans } from "../lib/schematicMap";
import { errorMessage, hasActiveFilters } from "../lib/drawingMapPanel";
import type { LoadState } from "./useDrawingMapResources";

type Params = {
  projectId: string;
  batchId?: string | null;
  compact: boolean;
  primaryZone?: string | null;
  refreshKey: number;
  lazyReady: boolean;
};

function stageForRow(row: ProgressRow) {
  const eventStageId = row.construction_event?.stage_id ?? row.stage_id;
  return (
    (eventStageId
      ? row.stages.find((stage) => stage.id === eventStageId)
      : null) ??
    row.stages.find((stage) => stage.latest_event_at) ??
    row.stages[0] ??
    null
  );
}

export function useSchematicMapResources({
  projectId,
  batchId,
  compact,
  primaryZone,
  refreshKey,
  lazyReady,
}: Params) {
  const [rows, setRows] = useState<ProgressRow[]>([]);
  const [works, setWorks] = useState<MainWork[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [filters, setFilters] = useState<DrawingFilters>({
    ...EMPTY_DRAWING_FILTERS,
  });
  const [activeSheetId, setActiveSheetId] = useState("");
  const [imageBox, setImageBox] = useState<ImageBox | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoadState("loading");
    setLoadError(null);
    Promise.all([
      listComponentProgress(projectId, undefined, batchId),
      fetchMainWorks(projectId),
    ])
      .then(([progressRows, catalog]) => {
        if (controller.signal.aborted) return;
        setRows(progressRows);
        setWorks(catalog.works);
        setLoadState("ready");
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(errorMessage(error));
        setLoadState("error");
      });
    return () => controller.abort();
  }, [projectId, batchId, reloadKey, refreshKey]);

  const map = useMemo<DrawingMap>(() => {
    const rowById = new Map(rows.map((row) => [row.id, row]));
    const plans = buildSchematicPlans(
      rows.map((row) => ({
        id: row.id,
        code: row.canonical_code,
        type: row.type,
        zone: row.zone,
        segment: row.segment_number,
        status: row.construction_status,
        accepted:
          row.acceptance_status === "APPROVED" ||
          row.acceptance_status === "CONFIRMED",
        designGroup: row.design_group,
      })),
    );
    const sheets: DrawingSheet[] = plans.map((plan) => {
      const markers: DrawingMarker[] = plan.markers.flatMap((geometry) => {
        const row = rowById.get(geometry.componentId);
        if (!row) return [];
        const stage = stageForRow(row);
        const preferred =
          stage && mainWorkForDefinition(works, stage.stage_definition_id)
            ? mainWorkForDefinition(works, stage.stage_definition_id)
            : row.stages
                .map((item) => mainWorkForDefinition(works, item.stage_definition_id))
                .find(Boolean) ?? null;
        const workName = preferred?.label ?? stage?.name ?? null;
        return [{
          component_id: row.id,
          code: row.canonical_code,
          type: row.type,
          zone: row.zone,
          segment: row.segment_number,
          design_group: row.design_group,
          location_review: false,
          current_work: workName,
          current_work_definition_id: stage?.stage_definition_id ?? null,
          current_work_name: workName,
          current_work_status: row.construction_status,
          current_stage_name: stage?.name ?? null,
          current_stage_definition_id: stage?.stage_definition_id ?? null,
          last_event_date: row.construction_event?.event_date ?? null,
          accepted: row.acceptance_status === "APPROVED" ||
            row.acceptance_status === "CONFIRMED",
          points: geometry.points,
          origin: row.scopes.includes("ADDITIONAL_SCOPE")
            ? "ADDITIONAL_SCOPE"
            : "DESIGN_SCOPE",
          construction_status: row.construction_status,
          position_id: null,
          position_status: null,
          position_note: null,
        }];
      });
      return {
        id: plan.key,
        title: plan.title,
        drawing: "Sơ đồ",
        page: 0,
        image_url: "",
        zone: plan.zone,
        segment: plan.segment,
        markers,
        schematic: plan,
      };
    });
    return {
      sheets,
      review_count: 0,
      position_review_count: 0,
    };
  }, [rows, works]);

  const filteredSheets = useMemo(() => {
    const sheets = filterDrawingSheets(map.sheets, filters);
    return compact ? sheets.filter((sheet) => sheet.markers.length > 0) : sheets;
  }, [map, filters, compact]);

  const activeSheet = useMemo(
    () =>
      filteredSheets.find((sheet) => sheet.id === activeSheetId) ??
      filteredSheets[0] ??
      null,
    [filteredSheets, activeSheetId],
  );

  useEffect(() => {
    if (!map.sheets.length) {
      setActiveSheetId("");
      return;
    }
    setActiveSheetId((current) => {
      if (map.sheets.some((sheet) => sheet.id === current)) return current;
      const preferred = compact
        ? pickPrimarySheet(map.sheets, primaryZone)
        : map.sheets[0];
      return preferred?.id ?? "";
    });
  }, [map, compact, primaryZone]);

  const visibleMarkerCount = useMemo(
    () => countMarkers(filteredSheets),
    [filteredSheets],
  );
  const allMarkerCount = useMemo(
    () => countMarkers(map.sheets),
    [map],
  );
  const retryLoad = useCallback(() => setReloadKey((value) => value + 1), []);
  const hasFilters = hasActiveFilters(filters);
  const imageReady = loadState === "ready" && Boolean(activeSheet);
  const imageInView = !compact || lazyReady;

  return {
    map,
    rows,
    loadState,
    loadError,
    retryLoad,
    filters,
    updateFilter: (patch: Partial<DrawingFilters>) =>
      setFilters((current) => ({ ...current, ...patch })),
    clearFilters: () => setFilters({ ...EMPTY_DRAWING_FILTERS }),
    hasFilters,
    filteredSheets,
    activeSheet,
    setActiveSheetId,
    visibleMarkerCount,
    allMarkerCount,
    activeSheetKey: activeSheet?.id ?? "",
    activeImageUrl: "",
    imageInView,
    imageUrl: null,
    imageState:
      loadState === "error"
        ? ("error" as const)
        : imageReady
          ? ("ready" as const)
          : ("loading" as const),
    imageError: loadError,
    imageReloadKey: 0,
    retryImage: retryLoad,
    imageBox,
    setImageBox,
  };
}
