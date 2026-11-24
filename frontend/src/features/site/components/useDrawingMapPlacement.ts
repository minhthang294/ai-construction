/** Placement (draft map position) state and actions for the drawing map panel. */

import { useEffect, useState } from "react";
import {
  clientToSheetPoint,
  reviewDrawingMapPosition,
  sanitizePoints,
  saveDrawingMapPosition,
  type DrawingMarker,
  type ImageBox,
  type View,
} from "../lib/drawingMap";
import {
  errorMessage,
  nextPlacementPoints,
  placementSaveError,
  type Placement,
  type PlacementTarget,
} from "../lib/drawingMapPanel";

type Params = {
  projectId: string;
  activeSheetId: string;
  placementRequest?: PlacementTarget | null;
  onPlacementDone?: () => void;
  closeDetail: () => void;
  setDetailMarker: React.Dispatch<React.SetStateAction<DrawingMarker | null>>;
  retryLoad: () => void;
  viewportRef: React.RefObject<HTMLDivElement | null>;
  imageBox: ImageBox | null;
  viewRef: React.RefObject<View>;
};

export function useDrawingMapPlacement({
  projectId,
  activeSheetId,
  placementRequest,
  onPlacementDone,
  closeDetail,
  setDetailMarker,
  retryLoad,
  viewportRef,
  imageBox,
  viewRef,
}: Params) {
  const [placement, setPlacement] = useState<Placement | null>(null);
  const [placementBusy, setPlacementBusy] = useState(false);
  const [placementError, setPlacementError] = useState<string | null>(null);
  const [positionMessage, setPositionMessage] = useState<string | null>(null);
  const [positionError, setPositionError] = useState<string | null>(null);
  const [dragPointIndex, setDragPointIndex] = useState<number | null>(null);
  const [reviewBusyId, setReviewBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!placementRequest) return;
    setPlacement({
      ...placementRequest,
      sheetId: activeSheetId,
      points: [],
      override: false,
    });
    setPlacementError(null);
    setPositionMessage(null);
    setPositionError(null);
  }, [placementRequest, activeSheetId]);

  function placementPointAt(event: {
    clientX: number;
    clientY: number;
  }): [number, number] | null {
    const viewport = viewportRef.current;
    if (!viewport || !imageBox) return null;
    const rect = viewport.getBoundingClientRect();
    return clientToSheetPoint(
      { x: event.clientX, y: event.clientY },
      rect,
      imageBox,
      viewRef.current,
    );
  }

  function addPlacementPoint(event: { clientX: number; clientY: number }) {
    const point = placementPointAt(event);
    if (!point) return;
    setPlacement((current) => {
      if (!current) return current;
      const points = nextPlacementPoints(current, point);
      if (points === current.points) return current;
      return { ...current, points };
    });
    setPlacementError(null);
  }

  function updatePlacementPoint(
    index: number,
    event: { clientX: number; clientY: number },
  ) {
    const point = placementPointAt(event);
    if (!point) return;
    setPlacement((current) => {
      if (!current) return current;
      return {
        ...current,
        points: current.points.map((existing, currentIndex) =>
          currentIndex === index ? point : existing,
        ),
      };
    });
  }

  function removeLastPlacementPoint() {
    setPlacement((current) =>
      current
        ? { ...current, points: current.points.slice(0, -1) }
        : current,
    );
  }

  async function savePlacement() {
    if (!placement) return;
    const validationError = placementSaveError(placement);
    if (validationError) {
      setPlacementError(validationError);
      return;
    }
    setPlacementBusy(true);
    setPlacementError(null);
    try {
      await saveDrawingMapPosition(projectId, placement.componentId, {
        sheet_id: placement.sheetId,
        points: placement.points,
        note: placement.override ? "Ghi đè vị trí thiết kế" : null,
      });
      setPlacement(null);
      setPositionMessage(
        `Đã lưu vị trí nháp cho ${placement.code}. Quản lý dự án sẽ duyệt lại.`,
      );
      retryLoad();
      onPlacementDone?.();
    } catch (error) {
      setPlacementError(errorMessage(error));
    } finally {
      setPlacementBusy(false);
    }
  }

  function cancelPlacement() {
    setPlacement(null);
    setPlacementError(null);
    onPlacementDone?.();
  }

  function startOverride(marker: DrawingMarker) {
    setPlacement({
      componentId: marker.component_id,
      code: marker.code,
      type: marker.type,
      sheetId: activeSheetId,
      points: sanitizePoints(marker.points),
      override: true,
    });
    setPlacementError(null);
    setPositionMessage(null);
    setPositionError(null);
    closeDetail();
  }

  async function reviewPosition(marker: DrawingMarker) {
    if (!activeSheetId) return;
    setReviewBusyId(marker.component_id);
    setPositionError(null);
    try {
      await reviewDrawingMapPosition(projectId, marker.component_id, activeSheetId);
      setDetailMarker((current) =>
        current && current.component_id === marker.component_id
          ? { ...current, position_status: "REVIEWED" }
          : current,
      );
      setPositionMessage(`Đã duyệt vị trí ${marker.code}.`);
      retryLoad();
    } catch (error) {
      setPositionError(errorMessage(error));
    } finally {
      setReviewBusyId(null);
    }
  }

  return {
    placement,
    placementBusy,
    placementError,
    positionMessage,
    positionError,
    dragPointIndex,
    setDragPointIndex,
    reviewBusyId,
    addPlacementPoint,
    updatePlacementPoint,
    removeLastPlacementPoint,
    savePlacement,
    cancelPlacement,
    startOverride,
    reviewPosition,
  };
}

export type DrawingMapPlacement = ReturnType<typeof useDrawingMapPlacement>;
