/** Component detail drawer state for the drawing map panel. */

import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  fetchComponentDetail,
  type ComponentDetail,
  type DrawingMarker,
} from "../lib/drawingMap";
import { errorMessage } from "../lib/drawingMapPanel";

export type DetailState = "idle" | "loading" | "ready" | "error";

type Params = {
  projectId: string;
  compact: boolean;
};

export function useDrawingMapDetail({ projectId, compact }: Params) {
  const [detailMarker, setDetailMarker] = useState<DrawingMarker | null>(null);
  const [detail, setDetail] = useState<ComponentDetail | null>(null);
  const [detailState, setDetailState] = useState<DetailState>("idle");
  const [detailError, setDetailError] = useState<string | null>(null);
  const detailRequest = useRef(0);

  const detailHeadingRef = useRef<HTMLHeadingElement>(null);
  const detailHeadingId = useId();

  useEffect(() => {
    detailRequest.current += 1;
    setDetailMarker(null);
    setDetail(null);
    setDetailState("idle");
    setDetailError(null);
  }, [projectId]);

  useEffect(
    () => () => {
      detailRequest.current += 1;
    },
    [],
  );

  useEffect(() => {
    if (!detailMarker) return;
    const heading = detailHeadingRef.current;
    if (!heading) return;
    heading.focus({ preventScroll: true });
    heading.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [detailMarker]);

  const closeDetail = useCallback(() => {
    detailRequest.current += 1;
    setDetailMarker(null);
    setDetail(null);
    setDetailState("idle");
    setDetailError(null);
  }, []);

  useEffect(() => {
    if (!detailMarker) return;
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") closeDetail();
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [detailMarker, closeDetail]);

  async function openDetail(marker: DrawingMarker) {
    const requestId = ++detailRequest.current;
    setDetailMarker(marker);
    setDetail(null);
    setDetailError(null);
    if (compact) {
      setDetailState("idle");
      return;
    }
    setDetailState("loading");
    setDetailError(null);
    try {
      const data = await fetchComponentDetail(projectId, marker.component_id);
      if (requestId !== detailRequest.current) return;
      setDetail(data);
      setDetailState("ready");
    } catch (error) {
      if (requestId !== detailRequest.current) return;
      setDetailError(errorMessage(error));
      setDetailState("error");
    }
  }

  return {
    detailMarker,
    setDetailMarker,
    detail,
    detailState,
    detailError,
    detailHeadingRef,
    detailHeadingId,
    openDetail,
    closeDetail,
  };
}

export type DrawingMapDetail = ReturnType<typeof useDrawingMapDetail>;
