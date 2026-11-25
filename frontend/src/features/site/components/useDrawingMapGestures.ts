/** Pointer drag/pinch handling for the drawing map viewport. */

import { useEffect, useRef } from "react";
import {
  MAX_ZOOM,
  MIN_ZOOM,
  clampPan,
  clampZoom,
  pinchView,
  pinchZoom,
  viewTransform,
  zoomAroundPoint,
  type Pan,
  type View,
} from "../lib/drawingMap";
import { pointerDistance } from "../lib/drawingMapPanel";
import type { SetView } from "./useDrawingMapViewport";

type GestureState = {
  mode: "none" | "drag" | "pinch";
  pointers: Map<number, Pan>;
  start: Pan;
  startView: View;
  pinchDistance: number;
  pinchStartMid: Pan;
  moved: boolean;
  lastMove: Pan;
  lastMoveAt: number;
  velocity: Pan;
  pendingView: View | null;
  frame: number | null;
  inertiaFrame: number | null;
  lastTap: { time: number; point: Pan } | null;
};

const TAP_SLOP_PX = 6;
const DOUBLE_TAP_MS = 300;
const DOUBLE_TAP_PX = 24;
const INERTIA_STOP = 0.02;

type Params = {
  viewRef: React.RefObject<View>;
  viewportRef: React.RefObject<HTMLDivElement | null>;
  contentRef: React.RefObject<HTMLDivElement | null>;
  setView: SetView;
  placementActive: boolean;
  addPlacementPoint: (event: { clientX: number; clientY: number }) => void;
  onTap: (clientX: number, clientY: number) => void;
};

export function useDrawingMapGestures({
  viewRef,
  viewportRef,
  contentRef,
  setView,
  placementActive,
  addPlacementPoint,
  onTap,
}: Params) {
  const gesture = useRef<GestureState>({
    mode: "none",
    pointers: new Map(),
    start: { x: 0, y: 0 },
    startView: { zoom: 1, pan: { x: 0, y: 0 } },
    pinchDistance: 0,
    pinchStartMid: { x: 0, y: 0 },
    moved: false,
    lastMove: { x: 0, y: 0 },
    lastMoveAt: 0,
    velocity: { x: 0, y: 0 },
    pendingView: null,
    frame: null,
    inertiaFrame: null,
    lastTap: null,
  });

  function viewportRect(): DOMRect | null {
    return viewportRef.current?.getBoundingClientRect() ?? null;
  }

  function applyView(next: View) {
    viewRef.current = next;
    const element = contentRef.current;
    if (element) element.style.transform = viewTransform(next);
  }

  function flushPending() {
    const state = gesture.current;
    if (state.frame !== null) {
      cancelAnimationFrame(state.frame);
      state.frame = null;
    }
    if (state.pendingView) {
      applyView(state.pendingView);
      state.pendingView = null;
    }
  }

  function commitView() {
    flushPending();
    setView(viewRef.current);
  }

  function scheduleView(next: View) {
    const state = gesture.current;
    state.pendingView = next;
    if (state.frame !== null) return;
    state.frame = requestAnimationFrame(() => {
      state.frame = null;
      const pending = state.pendingView;
      state.pendingView = null;
      if (pending) applyView(pending);
    });
  }

  function stopInertia() {
    const state = gesture.current;
    if (state.inertiaFrame !== null) {
      cancelAnimationFrame(state.inertiaFrame);
      state.inertiaFrame = null;
    }
  }

  function beginDrag(point: Pan) {
    const state = gesture.current;
    state.mode = "drag";
    state.start = point;
    state.startView = viewRef.current;
    state.moved = false;
    state.lastMove = point;
    state.lastMoveAt = performance.now();
    state.velocity = { x: 0, y: 0 };
  }

  function handleTap(clientX: number, clientY: number) {
    const state = gesture.current;
    const now = performance.now();
    const last = state.lastTap;
    if (
      last &&
      now - last.time <= DOUBLE_TAP_MS &&
      Math.hypot(clientX - last.point.x, clientY - last.point.y) <=
        DOUBLE_TAP_PX
    ) {
      state.lastTap = null;
      const rect = viewportRect();
      if (!rect) return;
      const current = viewRef.current;
      const target =
        current.zoom >= MAX_ZOOM - 0.05
          ? MIN_ZOOM
          : clampZoom(current.zoom * 2);
      applyView(
        zoomAroundPoint(current, { x: clientX, y: clientY }, target, rect),
      );
      setView(viewRef.current);
      return;
    }
    state.lastTap = { time: now, point: { x: clientX, y: clientY } };
    onTap(clientX, clientY);
  }

  function startInertia() {
    const state = gesture.current;
    const rect = viewportRect();
    if (!rect || Math.hypot(state.velocity.x, state.velocity.y) < 0.08) {
      commitView();
      return;
    }
    let last = performance.now();
    const velocity = { ...state.velocity };
    const step = (now: number) => {
      const dt = Math.min(48, Math.max(1, now - last));
      last = now;
      const decay = Math.pow(0.92, dt / 16.667);
      velocity.x *= decay;
      velocity.y *= decay;
      const current = viewRef.current;
      const nextPan = clampPan(
        {
          x: current.pan.x + velocity.x * dt,
          y: current.pan.y + velocity.y * dt,
        },
        current.zoom,
        rect.width,
        rect.height,
      );
      const moved =
        nextPan.x !== current.pan.x || nextPan.y !== current.pan.y;
      applyView({ zoom: current.zoom, pan: nextPan });
      if (!moved || Math.hypot(velocity.x, velocity.y) < INERTIA_STOP) {
        state.inertiaFrame = null;
        commitView();
        return;
      }
      state.inertiaFrame = requestAnimationFrame(step);
    };
    state.inertiaFrame = requestAnimationFrame(step);
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    stopInertia();
    flushPending();
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
      state.moved = true;
      state.startView = viewRef.current;
      state.pinchDistance = pointerDistance(first, second);
      state.pinchStartMid = {
        x: (first.x + second.x) / 2,
        y: (first.y + second.y) / 2,
      };
    }
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const state = gesture.current;
    if (!state.pointers.has(event.pointerId)) return;
    state.pointers.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
    });
    const rect = viewportRect();
    if (!rect) return;

    if (state.mode === "pinch" && state.pointers.size >= 2) {
      const [first, second] = Array.from(state.pointers.values());
      const midpoint = {
        x: (first.x + second.x) / 2,
        y: (first.y + second.y) / 2,
      };
      scheduleView(
        pinchView(
          state.startView,
          state.pinchStartMid,
          midpoint,
          pinchZoom(
            state.startView.zoom,
            state.pinchDistance,
            pointerDistance(first, second),
          ),
          rect,
        ),
      );
      return;
    }

    if (state.mode === "drag" && state.pointers.size === 1) {
      const dx = event.clientX - state.start.x;
      const dy = event.clientY - state.start.y;
      if (!state.moved && Math.hypot(dx, dy) > TAP_SLOP_PX) {
        state.moved = true;
        state.lastTap = null;
      }
      const now = performance.now();
      const elapsed = now - state.lastMoveAt;
      if (state.moved && elapsed > 0) {
        state.velocity = {
          x: (event.clientX - state.lastMove.x) / elapsed,
          y: (event.clientY - state.lastMove.y) / elapsed,
        };
      }
      state.lastMove = { x: event.clientX, y: event.clientY };
      state.lastMoveAt = now;
      scheduleView({
        zoom: state.startView.zoom,
        pan: clampPan(
          {
            x: state.startView.pan.x + dx,
            y: state.startView.pan.y + dy,
          },
          state.startView.zoom,
          rect.width,
          rect.height,
        ),
      });
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

    if (wasSingleTap) {
      if (placementActive) addPlacementPoint(event);
      else handleTap(event.clientX, event.clientY);
    }

    if (state.pointers.size === 1) {
      flushPending();
      beginDrag(Array.from(state.pointers.values())[0]);
      state.moved = true;
      return;
    }
    if (state.pointers.size > 1) return;

    const finishedMode = state.mode;
    state.mode = "none";
    flushPending();
    if (finishedMode === "drag" && state.moved) {
      if (performance.now() - state.lastMoveAt > 80) {
        state.velocity = { x: 0, y: 0 };
      }
      startInertia();
    } else {
      commitView();
    }
  }

  function cancelPointer(event: React.PointerEvent<HTMLDivElement>) {
    const state = gesture.current;
    state.pointers.delete(event.pointerId);
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (state.pointers.size === 1) {
      flushPending();
      beginDrag(Array.from(state.pointers.values())[0]);
      state.moved = true;
      return;
    }
    if (state.pointers.size > 1) return;
    state.mode = "none";
    commitView();
  }

  useEffect(() => {
    const state = gesture.current;
    return () => {
      if (state.frame !== null) cancelAnimationFrame(state.frame);
      if (state.inertiaFrame !== null) cancelAnimationFrame(state.inertiaFrame);
    };
  }, []);

  return {
    handlePointerDown,
    handlePointerMove,
    endPointer,
    cancelPointer,
  };
}
