/** Zoom/pan state and viewport effects for the drawing map panel. */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  clampPan,
  clampZoom,
  fitViewToBounds,
  markerBounds,
  zoomAroundPoint,
  type DrawingSheet,
  type ImageBox,
  type View,
} from "../lib/drawingMap";
import type { ImageState } from "./useDrawingMapResources";

export type SetView = (next: View | ((current: View) => View)) => void;

type Params = {
  activeImageUrl: string;
  imageReloadKey: number;
  activeSheetKey: string;
  activeSheet: DrawingSheet | null;
  imageState: ImageState;
  imageBox: ImageBox | null;
  viewportRef: React.RefObject<HTMLDivElement | null>;
};

export function useDrawingMapViewport({
  activeImageUrl,
  imageReloadKey,
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
  const setView = useCallback((next: View | ((current: View) => View)) => {
    const value = typeof next === "function" ? next(viewRef.current) : next;
    viewRef.current = value;
    setViewState(value);
  }, []);

  useEffect(() => {
    if (!activeImageUrl) return;
    setView({ zoom: 1, pan: { x: 0, y: 0 } });
  }, [activeImageUrl, imageReloadKey, setView]);

  useEffect(() => {
    if (imageState !== "ready" || !imageBox || !activeSheet) return;
    const viewport = viewportRef.current;
    if (!viewport) return;
    const fitted = fitViewToBounds(
      markerBounds(activeSheet.markers),
      imageBox,
      viewport.clientWidth,
      viewport.clientHeight,
      0.08,
    );
    const next = fitted ?? { zoom: 1, pan: { x: 0, y: 0 } };
    setFitView(next);
    setView(next);
  }, [activeSheetKey, imageBox, imageState, setView]);

  useEffect(() => {
    if (imageState !== "ready" || !activeSheetKey) return;
    const element = viewportRef.current;
    if (!element) return;
    function handleWheel(event: WheelEvent) {
      if (!element) return;
      event.preventDefault();
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
  }, [activeSheetKey, imageState, setView]);

  function viewportSize(): { width: number; height: number } {
    const element = viewportRef.current;
    return {
      width: element?.clientWidth ?? 0,
      height: element?.clientHeight ?? 0,
    };
  }

  function zoomBy(delta: number) {
    const next = clampZoom(viewRef.current.zoom + delta);
    const { width, height } = viewportSize();
    setView((current) => ({
      zoom: next,
      pan: clampPan(current.pan, next, width, height),
    }));
  }

  function resetView() {
    setView(fitView);
  }

  function showWholeSheet() {
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
  };
}

export type DrawingMapViewport = ReturnType<typeof useDrawingMapViewport>;
