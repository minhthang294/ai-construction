/** Pointer drag/pinch handling for the drawing map viewport. */

import { useRef } from "react";
import { clampPan, pinchZoom, type Pan } from "../lib/drawingMap";
import { pointerDistance } from "../lib/drawingMapPanel";
import type { SetView } from "./useDrawingMapViewport";

type GestureState = {
  mode: "none" | "drag" | "pinch";
  pointers: Map<number, Pan>;
  start: Pan;
  startPan: Pan;
  moved: boolean;
  pinchDistance: number;
  pinchStartZoom: number;
};

type Params = {
  viewRef: React.RefObject<{ zoom: number; pan: Pan }>;
  viewportRef: React.RefObject<HTMLDivElement | null>;
  setView: SetView;
  placementActive: boolean;
  addPlacementPoint: (event: { clientX: number; clientY: number }) => void;
};

export function useDrawingMapGestures({
  viewRef,
  viewportRef,
  setView,
  placementActive,
  addPlacementPoint,
}: Params) {
  const gesture = useRef<GestureState>({
    mode: "none",
    pointers: new Map(),
    start: { x: 0, y: 0 },
    startPan: { x: 0, y: 0 },
    moved: false,
    pinchDistance: 0,
    pinchStartZoom: 1,
  });

  function viewportSize(): { width: number; height: number } {
    const element = viewportRef.current;
    return {
      width: element?.clientWidth ?? 0,
      height: element?.clientHeight ?? 0,
    };
  }

  function beginDrag(point: Pan) {
    gesture.current.mode = "drag";
    gesture.current.start = point;
    gesture.current.startPan = viewRef.current.pan;
    gesture.current.moved = false;
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    const element = event.currentTarget;
    element.setPointerCapture?.(event.pointerId);
    const state = gesture.current;
    const point = { x: event.clientX, y: event.clientY };
    state.pointers.set(event.pointerId, point);
    if (state.pointers.size === 1) {
      beginDrag(point);
      return;
    }
    if (state.pointers.size === 2) {
      const [first, second] = Array.from(state.pointers.values());
      state.mode = "pinch";
      state.pinchDistance = pointerDistance(first, second);
      state.pinchStartZoom = viewRef.current.zoom;
    }
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const state = gesture.current;
    if (!state.pointers.has(event.pointerId)) return;
    state.pointers.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
    });
    const { width, height } = viewportSize();
    if (state.mode === "pinch" && state.pointers.size >= 2) {
      const [first, second] = Array.from(state.pointers.values());
      const next = pinchZoom(
        state.pinchStartZoom,
        state.pinchDistance,
        pointerDistance(first, second),
      );
      setView((current) => ({
        zoom: next,
        pan: clampPan(current.pan, next, width, height),
      }));
      return;
    }
    if (state.mode === "drag" && state.pointers.size === 1) {
      if (
        Math.hypot(
          event.clientX - state.start.x,
          event.clientY - state.start.y,
        ) > 6
      ) {
        state.moved = true;
      }
      setView((current) => ({
        zoom: current.zoom,
        pan: clampPan(
          {
            x: state.startPan.x + (event.clientX - state.start.x),
            y: state.startPan.y + (event.clientY - state.start.y),
          },
          current.zoom,
          width,
          height,
        ),
      }));
    }
  }

  function endPointer(event: React.PointerEvent<HTMLDivElement>) {
    const state = gesture.current;
    const wasSingleTap =
      state.pointers.size === 1 && state.mode === "drag" && !state.moved;
    state.pointers.delete(event.pointerId);
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (wasSingleTap && placementActive) {
      addPlacementPoint(event);
    }
    if (state.pointers.size === 1) {
      beginDrag(Array.from(state.pointers.values())[0]);
      state.moved = true;
    } else if (state.pointers.size === 0) {
      state.mode = "none";
    }
  }

  return { handlePointerDown, handlePointerMove, endPointer };
}
