/** Map/filters/image loading state for the drawing map panel. */

import { useEffect, useMemo, useState } from "react";
import {
  EMPTY_DRAWING_FILTERS,
  containBox,
  countMarkers,
  fetchDrawingMap,
  fetchDrawingSheetImageUrl,
  filterDrawingSheets,
  pickPrimarySheet,
  type DrawingFilters,
  type DrawingMap,
  type ImageBox,
} from "../lib/drawingMap";
import {
  errorMessage,
  hasActiveFilters,
  isPending,
} from "../lib/drawingMapPanel";

export type LoadState = "loading" | "ready" | "pending" | "error";
export type ImageState = "idle" | "loading" | "ready" | "error";

type Params = {
  projectId: string;
  batchId?: string | null;
  compact: boolean;
  primaryZone?: string | null;
  refreshKey: number;
  lazyReady: boolean;
  rootRef: React.RefObject<HTMLElement | null>;
  imageRef: React.RefObject<HTMLImageElement | null>;
};

export function useDrawingMapResources({
  projectId,
  batchId,
  compact,
  primaryZone,
  refreshKey,
  lazyReady,
  rootRef,
  imageRef,
}: Params) {
  const [imageInView, setImageInView] = useState(!compact);
  const [map, setMap] = useState<DrawingMap | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [filters, setFilters] = useState<DrawingFilters>({
    ...EMPTY_DRAWING_FILTERS,
  });
  const [activeSheetId, setActiveSheetId] = useState("");

  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageState, setImageState] = useState<ImageState>("idle");
  const [imageError, setImageError] = useState<string | null>(null);
  const [imageReloadKey, setImageReloadKey] = useState(0);
  const [imageBox, setImageBox] = useState<ImageBox | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoadState("loading");
    setLoadError(null);
    setMap(null);
    fetchDrawingMap(projectId, batchId, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setMap(data);
        setLoadState("ready");
        setActiveSheetId((current) => {
          if (data.sheets.some((sheet) => sheet.id === current)) return current;
          const preferred = compact
            ? pickPrimarySheet(data.sheets, primaryZone)
            : data.sheets[0];
          return preferred?.id ?? "";
        });
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        if (isPending(error)) {
          setLoadState("pending");
          return;
        }
        setLoadError(errorMessage(error));
        setLoadState("error");
      });
    return () => controller.abort();
  }, [projectId, batchId, reloadKey, compact, primaryZone, refreshKey]);

  useEffect(() => {
    if (!compact || !map) return;
    const preferred = pickPrimarySheet(map.sheets, primaryZone);
    if (preferred) setActiveSheetId(preferred.id);
  }, [compact, map, primaryZone]);

  useEffect(() => {
    if (!compact) {
      setImageInView(true);
      return;
    }
    if (!lazyReady) return;
    const element = rootRef.current;
    if (!element || typeof IntersectionObserver === "undefined") {
      setImageInView(true);
      return;
    }
    let observer: IntersectionObserver | null = null;
    // Wait for async dashboard sections above to settle before deciding.
    const timer = window.setTimeout(() => {
      if (!element) return;
      const rect = element.getBoundingClientRect();
      if (rect.top < window.innerHeight + 160 && rect.bottom > -160) {
        setImageInView(true);
        return;
      }
      observer = new IntersectionObserver(
        (entries) => {
          if (entries.some((entry) => entry.isIntersecting)) {
            setImageInView(true);
            observer?.disconnect();
          }
        },
        { rootMargin: "160px" },
      );
      observer.observe(element);
    }, 200);
    return () => {
      window.clearTimeout(timer);
      observer?.disconnect();
    };
  }, [compact, lazyReady, rootRef]);

  const filteredSheets = useMemo(() => {
    if (!map) return [];
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
  const visibleMarkerCount = useMemo(
    () => countMarkers(filteredSheets),
    [filteredSheets],
  );
  const activeImageUrl = imageInView ? activeSheet?.image_url ?? "" : "";
  const activeSheetKey = activeSheet?.id ?? "";
  const allMarkerCount = useMemo(
    () => countMarkers(map?.sheets ?? []),
    [map],
  );
  const hasFilters = hasActiveFilters(filters);

  useEffect(() => {
    if (!activeImageUrl) {
      setImageUrl(null);
      setImageState("idle");
      setImageError(null);
      setImageBox(null);
      return;
    }
    const controller = new AbortController();
    let created: string | null = null;
    setImageUrl(null);
    setImageState("loading");
    setImageError(null);
    setImageBox(null);
    fetchDrawingSheetImageUrl(activeImageUrl, controller.signal)
      .then((url) => {
        if (controller.signal.aborted) {
          URL.revokeObjectURL(url);
          return;
        }
        created = url;
        setImageUrl(url);
        setImageState("ready");
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setImageError(errorMessage(error));
        setImageState("error");
      });
    return () => {
      controller.abort();
      if (created) URL.revokeObjectURL(created);
    };
  }, [activeImageUrl, imageReloadKey]);

  useEffect(() => {
    if (imageState !== "ready") return;
    const image = imageRef.current;
    if (!image) return;
    const measure = () => {
      setImageBox(
        containBox(
          image.naturalWidth,
          image.naturalHeight,
          image.clientWidth,
          image.clientHeight,
        ),
      );
    };
    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(image);
    return () => observer.disconnect();
  }, [imageState, imageUrl, imageRef]);

  useEffect(() => {
    setFilters({ ...EMPTY_DRAWING_FILTERS });
    setActiveSheetId("");
  }, [projectId]);

  function updateFilter(patch: Partial<DrawingFilters>) {
    setFilters((current) => ({ ...current, ...patch }));
  }

  function clearFilters() {
    setFilters({ ...EMPTY_DRAWING_FILTERS });
  }

  return {
    map,
    loadState,
    loadError,
    retryLoad: () => setReloadKey((current) => current + 1),
    filters,
    updateFilter,
    clearFilters,
    hasFilters,
    filteredSheets,
    activeSheet,
    activeSheetId,
    setActiveSheetId,
    visibleMarkerCount,
    allMarkerCount,
    activeSheetKey,
    activeImageUrl,
    imageInView,
    imageUrl,
    imageState,
    imageError,
    imageReloadKey,
    retryImage: () => setImageReloadKey((current) => current + 1),
    imageBox,
    setImageBox,
  };
}

export type DrawingMapResources = ReturnType<typeof useDrawingMapResources>;
