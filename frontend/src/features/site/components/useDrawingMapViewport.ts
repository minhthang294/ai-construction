/** Zoom/pan state and viewport effects for the drawing map panel. */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  clampPan,
  clampZoom,
  fitViewToBounds,
  markerBounds,
  viewportFitStep,
  zoomAroundPoint,
  type DrawingSheet,
  type ImageBox,
  type View,
  type ViewportFitState,
} from "../lib/drawingMap";
import type { ImageState } from "./useDrawingMapResources";
import { SCHEMATIC_BOUNDS } from "../lib/schematicMap";

export type SetView = (next: View | ((current: View) => View)) => void;

type Params = {
  activeSheetKey: string;
  activeSheet: DrawingSheet | null;
  imageState: ImageState;
  imageBox: ImageBox | null;
  viewportRef: React.RefObject<HTMLDivElement | null>;
};

export function useDrawingMapViewport({
  activeSheetKey,
  activeSheet,
  imageState,
  imageBox,
  viewportRef,
}: Params) {
  const [view, setViewState] = useState<View>({
    zoom: 1,
    pan: { x: 0, y: 0 },
  });
  const [fitView, setFitView] = useState<View>({
    zoom: 1,
    pan: { x: 0, y: 0 },
  });
  const viewRef = useRef<View>(view);
  const fitStateRef = useRef<ViewportFitState>({
    activeSheetKey: "",
    fittedSheetKey: null,
  });
  const setView = useCallback((next: View | ((current: View) => View)) => {
    const value = typeof next === "function" ? next(viewRef.current) : next;
    viewRef.current = value;
    setViewState(value);
  }, []);

  const markUserInteraction = useCallback(() => {
    fitStateRef.current = viewportFitStep(fitStateRef.current, {
      type: "gesture",
    }).state;
  }, []);

  useEffect(() => {
    if (!activeSheetKey) return;
    const imageReady = imageState === "ready" && Boolean(imageBox);
    const step = viewportFitStep(fitStateRef.current, {
      type: "open",
      sheetKey: activeSheetKey,
      imageReady,
    });
    fitStateRef.current = step.state;
    if (!step.fit || !imageBox || !activeSheet) return;
    const viewport = viewportRef.current;
    if (!viewport) return;
    const fitted = fitViewToBounds(
      activeSheet.schematic
        ? SCHEMATIC_BOUNDS
        : markerBounds(activeSheet.markers),
      imageBox,
      viewport.clientWidth,
      viewport.clientHeight,
      activeSheet.schematic ? 0.02 : 0.08,
    );
    const next = fitted ?? { zoom: 1, pan: { x: 0, y: 0 } };
    setFitView(next);
    setView(next);
  }, [activeSheetKey, activeSheet, imageBox, imageState, setView]);

  useEffect(() => {
    if (imageState !== "ready" || !activeSheetKey) return;
    const element = viewportRef.current;
    if (!element) return;
    function handleWheel(event: WheelEvent) {
      if (!element) return;
      event.preventDefault();
      markUserInteraction();
      const next = clampZoom(viewRef.current.zoom + (event.deltaY < 0 ? 0.25 : -0.25));
      setView(
        zoomAroundPoint(
          viewRef.current,
          { x: event.clientX, y: event.clientY },
          next,
          element.getBoundingClientRect(),
        ),
      );
    }
    element.addEventListener("wheel", handleWheel, { passive: false });
    return () => element.removeEventListener("wheel", handleWheel);
  }, [activeSheetKey, imageState, setView, markUserInteraction]);

  function viewportSize(): { width: number; height: number } {
    const element = viewportRef.current;
    return {
      width: element?.clientWidth ?? 0,
      height: element?.clientHeight ?? 0,
    };
  }

  function zoomBy(delta: number) {
    markUserInteraction();
    const next = clampZoom(viewRef.current.zoom + delta);
    const { width, height } = viewportSize();
    setView((current) => ({
      zoom: next,
      pan: clampPan(current.pan, next, width, height),
    }));
  }

  function resetView() {
    if (!activeSheet || !imageBox) return;
    const step = viewportFitStep(fitStateRef.current, {
      type: "reset",
      imageReady: true,
    });
    fitStateRef.current = step.state;
    const { width, height } = viewportSize();
    const fitted = fitViewToBounds(
      activeSheet.schematic
        ? SCHEMATIC_BOUNDS
        : markerBounds(activeSheet.markers),
      imageBox,
      width,
      height,
      activeSheet.schematic ? 0.02 : 0.08,
    );
    const next = fitted ?? { zoom: 1, pan: { x: 0, y: 0 } };
    setFitView(next);
    setView(next);
  }

  function showWholeSheet() {
    markUserInteraction();
    setView({ zoom: 1, pan: { x: 0, y: 0 } });
  }

  return {
    view,
    setView,
    viewRef,
    fitView,
    zoomBy,
    resetView,
    showWholeSheet,
    markUserInteraction,
  };
}

export type DrawingMapViewport = ReturnType<typeof useDrawingMapViewport>;
