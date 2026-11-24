import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { ApiError } from "../lib/api";
import {
  EMPTY_DRAWING_FILTERS,
  MAX_ZOOM,
  MIN_ZOOM,
  clampPan,
  clampZoom,
  clientToSheetPoint,
  componentTypeLabel,
  constructionStatusLabel,
  constructionStatusColor,
  ACCEPTANCE_OUTLINE_COLOR,
  containBox,
  countMarkers,
  designGroupColor,
  fetchComponentDetail,
  fetchDrawingMap,
  fetchDrawingSheetImageUrl,
  filterDrawingSheets,
  fitViewToBounds,
  isAdditionalScope,
  markerBounds,
  originLabel,
  pickPrimarySheet,
  pinchZoom,
  reviewDrawingMapPosition,
  sanitizePoints,
  saveDrawingMapPosition,
  type ComponentDetail,
  type DrawingFilters,
  type DrawingMap,
  type DrawingMarker,
  type ImageBox,
  type Pan,
  type View,
} from "../lib/drawingMap";

type Selection = {
  selectedIds: string[];
  selectableIds: string[];
  disabled?: boolean;
  onToggle: (componentId: string) => void;
};

export type PlacementTarget = {
  componentId: string;
  code: string;
  type: "pile" | "beam";
};

type Placement = PlacementTarget & {
  sheetId: string;
  points: Array<[number, number]>;
  override: boolean;
};

type Props = {
  projectId: string;
  batchId?: string | null;
  selection?: Selection;
  onRequestProgress?: (componentId: string, stageDefinitionId?: string | null) => void;
  /** "compact" is the overview card; it hides filters/list and lazily loads the image. */
  variant?: "full" | "compact";
  primaryZone?: string | null;
  onOpenComponent?: (componentId: string) => void;
  onOpenFullScreen?: () => void;
  /** Compact card waits for surrounding async layout before it loads the image. */
  lazyReady?: boolean;
  /** Start placement for a component created on this screen. */
  placement?: PlacementTarget | null;
  onPlacementDone?: () => void;
  /** Bump after an external write so the map refetches. */
  refreshKey?: number;
};

type LoadState = "loading" | "ready" | "pending" | "error";
type ImageState = "idle" | "loading" | "ready" | "error";
type DetailState = "idle" | "loading" | "ready" | "error";

const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-700 focus-visible:ring-offset-2";

const FIELD =
  "mt-1 min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300 sm:text-sm";

const BUTTON =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 active:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400";

const PRIMARY_BUTTON =
  "min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-semibold text-white active:bg-slate-900 disabled:bg-slate-300";

const STATUS_CHIP: Record<string, string> = {
  NOT_STARTED: "app-status app-status--not-started",
  IN_PROGRESS: "app-status app-status--in-progress",
  COMPLETED: "app-status app-status--completed",
  BLOCKED: "app-status app-status--blocked",
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Không xác định được lỗi.";
}

function isPending(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.status === 404 || error.status === 405 || error.status === 501)
  );
}

function formatShortMapDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value;
}

function StatusChip({ status }: { status: string }) {
  return (
    <span className={STATUS_CHIP[status] ?? "app-status app-status--not-started"}>
      {constructionStatusLabel(status)}
    </span>
  );
}

function verificationLabel(value: string): string {
  if (value === "VERIFIED") return "Đã duyệt";
  if (value === "NEEDS_REVIEW") return "Chờ duyệt";
  return value;
}

function recordOriginLabel(value: string): string {
  if (value === "SEED_IMPORT") return "Nhập từ danh mục";
  if (value === "MANUAL_ENTRY") return "Nhập thủ công";
  return value;
}

function shortSha(value?: string | null): string {
  return value ? `${value.slice(0, 12)}…` : "—";
}

function markerLabel(marker: DrawingMarker): string {
  return [
    marker.code,
    componentTypeLabel(marker.type),
    constructionStatusLabel(marker.construction_status),
    originLabel(marker.origin),
  ].join(" · ");
}

type GestureState = {
  mode: "none" | "drag" | "pinch";
  pointers: Map<number, Pan>;
  start: Pan;
  startPan: Pan;
  moved: boolean;
  pinchDistance: number;
  pinchStartZoom: number;
};

export default function DrawingMapPanel({
  projectId,
  batchId,
  selection,
  onRequestProgress,
  variant = "full",
  primaryZone,
  onOpenComponent,
  onOpenFullScreen,
  lazyReady = true,
  placement: placementRequest,
  onPlacementDone,
  refreshKey = 0,
}: Props) {
  const compact = variant === "compact";
  const rootRef = useRef<HTMLElement>(null);
  const [imageInView, setImageInView] = useState(!compact);
  const [map, setMap] = useState<DrawingMap | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [filters, setFilters] = useState<DrawingFilters>({
    ...EMPTY_DRAWING_FILTERS,
  });
  const [activeSheetId, setActiveSheetId] = useState("");
  const [placement, setPlacement] = useState<Placement | null>(null);
  const [placementBusy, setPlacementBusy] = useState(false);
  const [placementError, setPlacementError] = useState<string | null>(null);
  const [positionMessage, setPositionMessage] = useState<string | null>(null);
  const [positionError, setPositionError] = useState<string | null>(null);
  const [dragPointIndex, setDragPointIndex] = useState<number | null>(null);
  const [reviewBusyId, setReviewBusyId] = useState<string | null>(null);

  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageState, setImageState] = useState<ImageState>("idle");
  const [imageError, setImageError] = useState<string | null>(null);
  const [imageReloadKey, setImageReloadKey] = useState(0);
  const [imageBox, setImageBox] = useState<ImageBox | null>(null);

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

  const [detailMarker, setDetailMarker] = useState<DrawingMarker | null>(null);
  const [detail, setDetail] = useState<ComponentDetail | null>(null);
  const [detailState, setDetailState] = useState<DetailState>("idle");
  const [detailError, setDetailError] = useState<string | null>(null);
  const detailRequest = useRef(0);

  const viewportRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const detailHeadingRef = useRef<HTMLHeadingElement>(null);
  const detailHeadingId = useId();
  const gesture = useRef<GestureState>({
    mode: "none",
    pointers: new Map(),
    start: { x: 0, y: 0 },
    startPan: { x: 0, y: 0 },
    moved: false,
    pinchDistance: 0,
    pinchStartZoom: 1,
  });

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
  }, [compact, lazyReady]);

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
  const mapTargets = useMemo(() => (activeSheet?.markers ?? []).flatMap((marker) => {
    const points = sanitizePoints(marker.points);
    if (!points.length) return [];
    const middle = Math.floor((points.length - 1) / 2);
    const [x, y] = points[middle];
    const [endX, endY] = points[middle + 1] ?? points[middle];
    return [{ marker, points, x: (x + endX) / 2, y: (y + endY) / 2 }];
  }).sort(
    (a, b) => Number(a.points.length === 1) - Number(b.points.length === 1),
  ), [activeSheet]);
  const allMarkerCount = useMemo(
    () => countMarkers(map?.sheets ?? []),
    [map],
  );
  const hasFilters = Boolean(
    filters.query.trim() ||
      filters.type ||
      filters.status ||
      filters.origin,
  );

  useEffect(() => {
    if (!placementRequest) return;
    setPlacement({
      ...placementRequest,
      sheetId: activeSheet?.id ?? "",
      points: [],
      override: false,
    });
    setPlacementError(null);
    setPositionMessage(null);
    setPositionError(null);
  }, [placementRequest, activeSheet?.id]);

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
    setView({ zoom: 1, pan: { x: 0, y: 0 } });
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
  }, [activeImageUrl, imageReloadKey, setView]);

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
  }, [imageState, imageUrl]);

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
      setView((current) => ({
        zoom: next,
        pan: clampPan(
          current.pan,
          next,
          element.clientWidth,
          element.clientHeight,
        ),
      }));
    }
    element.addEventListener("wheel", handleWheel, { passive: false });
    return () => element.removeEventListener("wheel", handleWheel);
  }, [activeSheetKey, imageState, setView]);

  useEffect(() => {
    setFilters({ ...EMPTY_DRAWING_FILTERS });
    setActiveSheetId("");
  }, [projectId]);

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

  function updateFilter(patch: Partial<DrawingFilters>) {
    setFilters((current) => ({ ...current, ...patch }));
  }

  function clearFilters() {
    setFilters({ ...EMPTY_DRAWING_FILTERS });
  }

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

  function beginDrag(point: Pan) {
    gesture.current.mode = "drag";
    gesture.current.start = point;
    gesture.current.startPan = viewRef.current.pan;
    gesture.current.moved = false;
  }

  function pointerDistance(a: Pan, b: Pan): number {
    return Math.hypot(a.x - b.x, a.y - b.y);
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
    if (wasSingleTap && placement) {
      addPlacementPoint(event);
    }
    if (state.pointers.size === 1) {
      beginDrag(Array.from(state.pointers.values())[0]);
      state.moved = true;
    } else if (state.pointers.size === 0) {
      state.mode = "none";
    }
  }

  function placementPointAt(event: { clientX: number; clientY: number }) {
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
      if (current.type === "pile") return { ...current, points: [point] };
      if (current.points.length >= 30) return current;
      return { ...current, points: [...current.points, point] };
    });
    setPlacementError(null);
  }

  function updatePlacementPoint(index: number, event: { clientX: number; clientY: number }) {
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

  async function savePlacement() {
    if (!placement) return;
    if (placement.type === "pile" && placement.points.length !== 1) {
      setPlacementError("Cọc cần đúng một điểm trên bản vẽ.");
      return;
    }
    if (placement.type === "beam" && placement.points.length < 2) {
      setPlacementError("Dầm cần ít nhất hai điểm để vẽ đường tim.");
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
      setReloadKey((current) => current + 1);
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
      sheetId: activeSheet?.id ?? "",
      points: sanitizePoints(marker.points),
      override: true,
    });
    setPlacementError(null);
    setPositionMessage(null);
    setPositionError(null);
    closeDetail();
  }

  async function reviewPosition(marker: DrawingMarker) {
    if (!activeSheet) return;
    setReviewBusyId(marker.component_id);
    setPositionError(null);
    try {
      await reviewDrawingMapPosition(
        projectId,
        marker.component_id,
        activeSheet.id,
      );
      setDetailMarker((current) =>
        current && current.component_id === marker.component_id
          ? { ...current, position_status: "REVIEWED" }
          : current,
      );
      setPositionMessage(`Đã duyệt vị trí ${marker.code}.`);
      setReloadKey((current) => current + 1);
    } catch (error) {
      setPositionError(errorMessage(error));
    } finally {
      setReviewBusyId(null);
    }
  }

  const reviewCount = map?.review_count ?? 0;

  return (
    <section
      ref={rootRef}
      className={compact ? "relative space-y-2" : "mx-auto w-full max-w-4xl space-y-3"}
    >
      {compact ? (
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-slate-950">Mặt bằng</h3>
            <p className="mt-0.5 text-xs leading-5 text-slate-600">
              {activeSheet
                ? `${activeSheet.title} · ${activeSheet.markers.length} vị trí`
                : "Vị trí cấu kiện trong đợt đang chọn."}
            </p>
          </div>
          {onOpenFullScreen ? (
            <button
              type="button"
              className={`${BUTTON} shrink-0 ${FOCUS_RING}`}
              onClick={onOpenFullScreen}
            >
              Mở toàn màn hình
            </button>
          ) : null}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          <h3 className="text-base font-semibold text-slate-900 sm:text-lg">
            Mặt bằng cấu kiện trên bản vẽ
          </h3>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            Bản đồ thử nghiệm cho các vị trí đã đối chiếu. Ảnh bản vẽ được tải
            riêng theo quyền công trình và không được lưu vào mã nguồn.
          </p>
          {loadState === "ready" && map ? (
            <p className="mt-2 text-xs text-slate-600">
              {map.sheets.length} trang bản vẽ · {allMarkerCount} vị trí đã gắn
            </p>
          ) : null}
          {selection ? (
            <p className="mt-2 rounded-lg border border-blue-200 bg-blue-50 p-2 text-xs text-blue-950" role="status">
              Đã chọn {selection.selectedIds.length} cấu kiện. Chạm vòng trên sơ đồ để chọn hoặc bỏ chọn; cấu kiện mờ không thuộc công việc này.
            </p>
          ) : null}
          {reviewCount > 0 ? (
            <p
              role="status"
              className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs leading-5 text-amber-950"
            >
              {reviewCount} mục cần rà soát và không hiển thị trên bản đồ.
            </p>
          ) : null}
          {(map?.position_review_count ?? 0) > 0 ? (
            <p
              role="status"
              className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs leading-5 text-amber-950"
            >
              {map?.position_review_count} vị trí Bunke đang hiển thị dạng nét đứt để chờ rà soát theo bản vẽ.
            </p>
          ) : null}
        </div>
      )}

      {positionMessage ? (
        <p
          role="status"
          className="rounded-xl border border-emerald-200 bg-emerald-50 p-2 text-xs leading-5 text-emerald-950"
        >
          {positionMessage}
        </p>
      ) : null}

      {positionError ? (
        <p
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 p-2 text-xs leading-5 text-red-900"
        >
          {positionError}
        </p>
      ) : null}

      {placement ? (
        <section className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
          <p className="font-semibold">
            {placement.override ? "Ghi đè vị trí" : "Đặt vị trí"} ·{" "}
            <span className="font-mono">{placement.code}</span>
          </p>
          <p className="mt-1 text-xs leading-5">
            {placement.sheetId
              ? `Trang đang đặt: ${activeSheet?.title ?? placement.sheetId}. `
              : "Hãy mở một trang bản vẽ còn hiển thị. "}
            {placement.type === "pile"
              ? "Chạm một điểm lên cọc, kéo điểm để chỉnh."
              : `Chạm ít nhất hai điểm dọc theo dầm (${placement.points.length} điểm), kéo từng điểm để chỉnh.`}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              className={`${PRIMARY_BUTTON} ${FOCUS_RING}`}
              disabled={
                placementBusy ||
                !placement.sheetId ||
                (placement.type === "pile"
                  ? placement.points.length !== 1
                  : placement.points.length < 2)
              }
              onClick={() => void savePlacement()}
            >
              {placementBusy ? "Đang lưu…" : "Lưu vị trí nháp"}
            </button>
            {placement.type === "beam" && placement.points.length > 0 ? (
              <button
                type="button"
                className={`${BUTTON} ${FOCUS_RING}`}
                disabled={placementBusy}
                onClick={() =>
                  setPlacement((current) =>
                    current
                      ? { ...current, points: current.points.slice(0, -1) }
                      : current,
                  )
                }
              >
                Xóa điểm cuối
              </button>
            ) : null}
            <button
              type="button"
              className={`${BUTTON} ${FOCUS_RING}`}
              disabled={placementBusy}
              onClick={cancelPlacement}
            >
              Hủy đặt vị trí
            </button>
          </div>
          {placementError ? (
            <p role="alert" className="mt-2 text-xs text-red-800">
              {placementError}
            </p>
          ) : null}
        </section>
      ) : null}

      {loadState === "loading" ? (
        <p className="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-600">
          Đang tải mặt bằng bản vẽ…
        </p>
      ) : null}

      {loadState === "pending" ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h4 className="text-base font-semibold text-slate-900">
            Mặt bằng bản vẽ đang được chuẩn bị
          </h4>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            Công trình này chưa có dữ liệu mặt bằng đã đối chiếu. Dữ liệu bản vẽ
            gốc không được tạo tự động.
          </p>
          <button
            type="button"
            className={`${BUTTON} mt-3 ${FOCUS_RING}`}
            onClick={() => setReloadKey((current) => current + 1)}
          >
            Kiểm tra lại
          </button>
        </div>
      ) : null}

      {loadState === "error" ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900"
        >
          <p>Không tải được mặt bằng bản vẽ: {loadError}</p>
          <button
            type="button"
            className={`${BUTTON} mt-3 ${FOCUS_RING}`}
            onClick={() => setReloadKey((current) => current + 1)}
          >
            Thử lại
          </button>
        </div>
      ) : null}

      {loadState === "ready" && map && (map.sheets.length === 0 || (compact && allMarkerCount === 0)) ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h4 className="text-base font-semibold text-slate-900">
            {compact ? "Đợt này chưa có vị trí trên bản vẽ" : "Chưa có bản đồ bản vẽ"}
          </h4>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {compact
              ? "Chưa có cấu kiện nào của đợt được gắn đúng vị trí trên trang bản vẽ đã đối chiếu."
              : "Công trình chưa có trang bản vẽ nào được gắn vị trí cấu kiện."}
          </p>
        </div>
      ) : null}

      {loadState === "ready" && map && map.sheets.length > 0 && !(compact && allMarkerCount === 0) ? (
        <>
          {!compact ? (
          <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="min-w-0 text-xs font-medium text-slate-700 sm:col-span-2">
                Tìm mã cấu kiện hoặc bản vẽ
                <input
                  type="search"
                  inputMode="search"
                  className={FIELD}
                  value={filters.query}
                  placeholder="Ví dụ F-24-25 hoặc TK-32"
                  onChange={(event) =>
                    updateFilter({ query: event.target.value })
                  }
                />
              </label>
              <label className="min-w-0 text-xs font-medium text-slate-700">
                Loại cấu kiện
                <select
                  className={FIELD}
                  value={filters.type}
                  onChange={(event) =>
                    updateFilter({ type: event.target.value })
                  }
                >
                  <option value="">Tất cả loại</option>
                  <option value="pile">Cọc</option>
                  <option value="beam">Dầm</option>
                </select>
              </label>
              <label className="min-w-0 text-xs font-medium text-slate-700">
                Trạng thái thi công
                <select
                  className={FIELD}
                  value={filters.status}
                  onChange={(event) =>
                    updateFilter({ status: event.target.value })
                  }
                >
                  <option value="">Tất cả trạng thái</option>
                  <option value="NOT_STARTED">Chưa bắt đầu</option>
                  <option value="IN_PROGRESS">Đang thi công</option>
                  <option value="COMPLETED">Hoàn thành</option>
                  <option value="BLOCKED">Tạm dừng</option>
                </select>
              </label>
              <label className="min-w-0 text-xs font-medium text-slate-700">
                Phạm vi sửa chữa
                <select
                  className={FIELD}
                  value={filters.origin}
                  onChange={(event) =>
                    updateFilter({ origin: event.target.value })
                  }
                >
                  <option value="">Tất cả phạm vi</option>
                  <option value="DESIGN_SCOPE">Thiết kế</option>
                  <option value="ADDITIONAL_SCOPE">Phát sinh</option>
                </select>
              </label>
              <div className="flex flex-wrap items-end justify-between gap-2 sm:col-span-2">
                <p aria-live="polite" className="text-xs text-slate-600">
                  {visibleMarkerCount} vị trí khớp bộ lọc
                </p>
                {hasFilters ? (
                  <button
                    type="button"
                    className={`${BUTTON} ${FOCUS_RING}`}
                    onClick={clearFilters}
                  >
                    Xóa lọc
                  </button>
                ) : null}
              </div>
            </div>
          </div>
          ) : null}

          {filteredSheets.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
              Không có cấu kiện khớp bộ lọc.
            </div>
          ) : (
            <>
              {!compact || filteredSheets.length > 1 ? (
              <div
                role="group"
                aria-label="Chọn trang bản vẽ"
                className="flex gap-2 overflow-x-auto pb-1"
              >
                {filteredSheets.map((sheet) => {
                  const selected = sheet.id === activeSheet?.id;
                  return (
                    <button
                      key={sheet.id}
                      type="button"
                      aria-pressed={selected}
                      disabled={Boolean(placement)}
                      className={`min-h-11 min-w-0 shrink-0 rounded-lg border px-3 text-left text-sm disabled:cursor-not-allowed disabled:opacity-60 ${
                        selected
                          ? "border-slate-700 bg-slate-800 text-white"
                          : "border-slate-300 bg-white text-slate-800"
                      } ${FOCUS_RING}`}
                      onClick={() => setActiveSheetId(sheet.id)}
                    >
                      <span className="block max-w-56 truncate font-semibold">
                        {sheet.title}
                      </span>
                      <span
                        className={`block text-xs ${
                          selected ? "text-slate-200" : "text-slate-500"
                        }`}
                      >
                        {sheet.drawing} · trang {sheet.page}
                      </span>
                    </button>
                  );
                })}
              </div>
              ) : null}

              {activeSheet ? (
                <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                  {!compact ? (
                  <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-200 p-3">
                    <div className="min-w-0">
                      <h4 className="break-words text-sm font-semibold text-slate-900">
                        {activeSheet.title}
                      </h4>
                      <p className="mt-0.5 text-xs text-slate-600">
                        Bản vẽ {activeSheet.drawing} · trang {activeSheet.page} ·{" "}
                        {activeSheet.markers.length} vị trí
                      </p>
                    </div>
                  </div>
                  ) : null}

                  <div
                    ref={viewportRef}
                    className={`relative touch-none select-none overflow-hidden bg-slate-100 ${
                      compact
                        ? "h-[34vh] min-h-56 max-h-[24rem] sm:h-[20rem]"
                        : "h-[62vh] min-h-64 max-h-[38rem]"
                    }`}
                    role="group"
                    aria-label="Bản đồ bản vẽ tương tác"
                    onPointerDown={handlePointerDown}
                    onPointerMove={handlePointerMove}
                    onPointerUp={endPointer}
                    onPointerCancel={endPointer}
                  >
                    {compact && !imageInView ? (
                      <p className="absolute inset-0 grid place-items-center p-4 text-center text-sm text-slate-600">
                        Cuộn tới để tải bản vẽ…
                      </p>
                    ) : null}

                    {imageState === "loading" ? (
                      <p className="absolute inset-0 grid place-items-center p-4 text-center text-sm text-slate-600">
                        Đang tải ảnh bản vẽ…
                      </p>
                    ) : null}

                    {imageState === "error" ? (
                      <div className="absolute inset-0 grid place-items-center p-4 text-center">
                        <div className="max-w-sm">
                          <p role="alert" className="text-sm text-red-900">
                            Không tải được ảnh bản vẽ: {imageError}
                          </p>
                          <button
                            type="button"
                            className={`${BUTTON} mt-3 ${FOCUS_RING}`}
                            onClick={() =>
                              setImageReloadKey((current) => current + 1)
                            }
                          >
                            Thử lại ảnh
                          </button>
                        </div>
                      </div>
                    ) : null}

                    {imageState === "ready" && imageUrl ? (
                      <div
                        className="absolute inset-0 will-change-transform"
                        style={{
                          transform: `translate(${view.pan.x}px, ${view.pan.y}px) scale(${view.zoom})`,
                        }}
                      >
                        <img
                          ref={imageRef}
                          src={imageUrl}
                          alt={`Bản vẽ ${activeSheet.drawing}, trang ${activeSheet.page}`}
                          className="h-full w-full object-contain"
                          draggable={false}
                          onLoad={() => {
                            const image = imageRef.current;
                            if (!image) return;
                            setImageBox(
                              containBox(
                                image.naturalWidth,
                                image.naturalHeight,
                                image.clientWidth,
                                image.clientHeight,
                              ),
                            );
                          }}
                        />
                        {imageBox ? (
                          <div
                            className="absolute"
                            style={{
                              left: imageBox.left,
                              top: imageBox.top,
                              width: imageBox.width,
                              height: imageBox.height,
                            }}
                          >
                            <svg
                              aria-hidden="true"
                              focusable="false"
                              viewBox="0 0 1 1"
                              preserveAspectRatio="none"
                              className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
                            >
                              {mapTargets.map(({ marker, points, x, y }) => {
                                const selected = selection
                                  ? selection.selectedIds.includes(marker.component_id)
                                  : detailMarker?.component_id === marker.component_id;
                                const selectable = !selection || selection.selectableIds.includes(marker.component_id);
                                const opacity = selection && !selectable ? 0.2 : 1;
                                const color = compact
                                  ? constructionStatusColor(marker.construction_status)
                                  : designGroupColor(marker.design_group) ??
                                    (marker.type === "beam" ? "#0f766e" : "#0369a1");
                                const accepted = Boolean(marker.accepted);
                                const path = points.map(([px, py]) => `${px},${py}`).join(" ");
                                return (
                                  <g key={`${marker.component_id}-${marker.code}`}>
                                    {points.length > 1 ? (
                                      <>
                                        {accepted ? (
                                          <polyline points={path} fill="none"
                                            stroke={ACCEPTANCE_OUTLINE_COLOR}
                                            strokeWidth={selected ? 4.5 : 3.25}
                                            strokeLinecap="round" strokeLinejoin="round"
                                            opacity={opacity}
                                            vectorEffect="non-scaling-stroke" />
                                        ) : null}
                                        <polyline points={path} fill="none" stroke="white"
                                          strokeWidth={selected ? 3.5 : 2.25}
                                          strokeLinecap="round" strokeLinejoin="round"
                                          opacity={opacity}
                                          vectorEffect="non-scaling-stroke" />
                                        <polyline points={path} fill="none"
                                          stroke={selected ? "#111827" : color}
                                          strokeWidth={selected ? 2 : 1.25}
                                          strokeLinecap="round" strokeLinejoin="round"
                                          strokeDasharray={marker.location_review || marker.position_status === "DRAFT" ? "2 3" : isAdditionalScope(marker) ? "5 3" : undefined}
                                          opacity={opacity}
                                          vectorEffect="non-scaling-stroke" />
                                      </>
                                    ) : (
                                      <>
                                        {accepted ? (
                                          <ellipse
                                            cx={x}
                                            cy={y}
                                            rx={0.006}
                                            ry={0.006 * imageBox.width / imageBox.height}
                                            fill="none"
                                            stroke={ACCEPTANCE_OUTLINE_COLOR}
                                            strokeWidth={selected ? 3 : 2}
                                            opacity={opacity}
                                            vectorEffect="non-scaling-stroke"
                                          />
                                        ) : null}
                                        <ellipse
                                          cx={x}
                                          cy={y}
                                          rx={0.004}
                                          ry={0.004 * imageBox.width / imageBox.height}
                                          fill="none"
                                          stroke={selected ? "#111827" : color}
                                          strokeWidth={selected ? 2 : 1.25}
                                          strokeDasharray={marker.location_review || marker.position_status === "DRAFT" ? "1.5 2" : isAdditionalScope(marker) ? "2 2" : undefined}
                                          opacity={opacity}
                                          vectorEffect="non-scaling-stroke"
                                        />
                                      </>
                                    )}
                                  </g>
                                );
                              })}
                            </svg>
                            {placement &&
                            placement.sheetId === activeSheet?.id &&
                            placement.points.length > 0 ? (
                              <svg
                                aria-hidden="true"
                                focusable="false"
                                viewBox="0 0 1 1"
                                preserveAspectRatio="none"
                                className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
                              >
                                {placement.points.length > 1 ? (
                                  <polyline
                                    points={placement.points
                                      .map(([x, y]) => `${x},${y}`)
                                      .join(" ")}
                                    fill="none"
                                    stroke="#b45309"
                                    strokeWidth={2}
                                    strokeDasharray="5 3"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    vectorEffect="non-scaling-stroke"
                                  />
                                ) : null}
                              </svg>
                            ) : null}
                            {mapTargets.map((target) => {
                              const { marker, x, y } = target;
                              // Keep a 32px screen-space hit area even at 100%.
                              const diameter = 32 / view.zoom;
                              const selected = selection
                                ? selection.selectedIds.includes(marker.component_id)
                                : detailMarker?.component_id === marker.component_id;
                              const selectable = !selection || selection.selectableIds.includes(marker.component_id);
                              return (
                                <button
                                  key={`${marker.component_id}-${marker.code}`}
                                  type="button"
                                  aria-label={selection
                                    ? `${selected ? "Bỏ chọn" : "Chọn"} ${markerLabel(marker)}${selectable ? "" : ", không phù hợp công việc"}`
                                    : `Mở chi tiết ${markerLabel(marker)}${marker.current_work ? `, đang làm ${marker.current_work}` : ""}`}
                                  aria-pressed={selected}
                                  className={`absolute z-10 -translate-x-1/2 -translate-y-1/2 rounded-full bg-transparent ${FOCUS_RING}`}
                                  disabled={Boolean(placement) || Boolean(selection && (selection.disabled || !selectable))}
                                  style={{
                                    left: `${x * 100}%`,
                                    top: `${y * 100}%`,
                                    width: diameter,
                                    height: diameter,
                                  }}
                                  onPointerDown={(event) =>
                                    event.stopPropagation()
                                  }
                                  onClick={() => selection
                                    ? selection.onToggle(marker.component_id)
                                    : void openDetail(marker)}
                                >
                                  {view.zoom >= 3 && marker.current_work ? (
                                    <span
                                      aria-hidden="true"
                                      className="pointer-events-none absolute left-1/2 top-full z-20 -translate-x-1/2 whitespace-normal rounded border border-slate-300 bg-white/95 px-1 py-0.5 text-center font-sans font-medium text-slate-800 shadow-sm"
                                      style={{
                                        width: `${132 / view.zoom}px`,
                                        marginTop: `${3 / view.zoom}px`,
                                        fontSize: `${10 / view.zoom}px`,
                                        lineHeight: `${12 / view.zoom}px`,
                                      }}
                                    >
                                      <span className="block font-bold">{marker.code}</span>
                                      <span className="block">Đang làm: {marker.current_work}</span>
                                    </span>
                                  ) : null}
                                </button>
                              );
                            })}
                            {placement &&
                            placement.sheetId === activeSheet?.id &&
                            placement.points.map(([x, y], index) => (
                              <button
                                key={`placement-${index}`}
                                type="button"
                                aria-label={`Điểm đặt vị trí ${index + 1}, kéo để chỉnh`}
                                className="absolute z-20 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-amber-600 bg-amber-200/80 shadow-sm"
                                style={{
                                  left: `${x * 100}%`,
                                  top: `${y * 100}%`,
                                  width: 28 / view.zoom,
                                  height: 28 / view.zoom,
                                  touchAction: "none",
                                }}
                                onPointerDown={(event) => {
                                  event.stopPropagation();
                                  event.currentTarget.setPointerCapture?.(
                                    event.pointerId,
                                  );
                                  setDragPointIndex(index);
                                }}
                                onPointerMove={(event) => {
                                  if (dragPointIndex !== index) return;
                                  event.stopPropagation();
                                  updatePlacementPoint(index, event);
                                }}
                                onPointerUp={(event) => {
                                  event.stopPropagation();
                                  setDragPointIndex(null);
                                  if (
                                    event.currentTarget.hasPointerCapture?.(
                                      event.pointerId,
                                    )
                                  ) {
                                    event.currentTarget.releasePointerCapture(
                                      event.pointerId,
                                    );
                                  }
                                }}
                                onPointerCancel={() => setDragPointIndex(null)}
                              />
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>

                  <div
                    role="group"
                    aria-label="Thu phóng bản vẽ"
                    className="flex flex-wrap items-center gap-1 border-t border-slate-200 bg-white px-2 py-1.5"
                  >
                    <button
                      type="button"
                      aria-label="Thu nhỏ bản vẽ"
                      className={`${BUTTON} min-w-11 px-0 ${FOCUS_RING}`}
                      disabled={view.zoom <= MIN_ZOOM}
                      onClick={() => zoomBy(-0.5)}
                    >
                      −
                    </button>
                    <span className="min-h-11 rounded-lg border border-slate-300 bg-white px-2 py-3 text-xs font-semibold text-slate-700">
                      {Math.round(view.zoom * 100)}%
                    </span>
                    <button
                      type="button"
                      aria-label="Phóng to bản vẽ"
                      className={`${BUTTON} min-w-11 px-0 ${FOCUS_RING}`}
                      disabled={view.zoom >= MAX_ZOOM}
                      onClick={() => zoomBy(0.5)}
                    >
                      +
                    </button>
                    <button
                      type="button"
                      aria-label="Vừa khung theo phạm vi cấu kiện"
                      className={`${BUTTON} ${FOCUS_RING}`}
                      onClick={resetView}
                    >
                      Vừa khung
                    </button>
                    <button
                      type="button"
                      aria-label="Xem toàn tờ bản vẽ"
                      className={`${BUTTON} ${FOCUS_RING}`}
                      onClick={showWholeSheet}
                    >
                      Toàn tờ
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-slate-200 p-3 text-xs text-slate-600">
                    {compact ? (
                      <>
                        <span>Kéo để di chuyển, chụm hai ngón hoặc dùng +/−.</span>
                        {[
                          ["NOT_STARTED", "Chưa bắt đầu"],
                          ["IN_PROGRESS", "Đang thi công"],
                          ["COMPLETED", "Hoàn thành"],
                          ["BLOCKED", "Tạm dừng"],
                        ].map(([status, label]) => (
                          <span key={status} className="inline-flex items-center gap-1">
                            <span
                              aria-hidden="true"
                              className="h-2.5 w-2.5 rounded-full"
                              style={{ backgroundColor: constructionStatusColor(status) }}
                            />
                            {label}
                          </span>
                        ))}
                        <span className="inline-flex items-center gap-1">
                          <span
                            aria-hidden="true"
                            className="h-3 w-3 rounded-full border-2"
                            style={{ borderColor: ACCEPTANCE_OUTLINE_COLOR }}
                          />
                          Đã nghiệm thu
                        </span>
                      </>
                    ) : (
                      <>
                        <span>Kéo để di chuyển.</span>
                        <span>Chụm hai ngón hoặc dùng nút +/− để thu phóng.</span>
                        <span className="inline-flex items-center gap-1"><span className="h-0.5 w-3 bg-teal-700" /> Dầm · nét mảnh</span>
                        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full border border-teal-700" /> Nhóm 1</span>
                        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full border border-amber-700" /> Nhóm 2</span>
                        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full border border-purple-700" /> Nhóm 3</span>
                        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full border border-dashed border-slate-600" /> Vị trí chờ rà soát</span>
                        <span className="inline-flex items-center gap-1">
                          <span className="h-2.5 w-2.5 rounded-full border border-dashed border-sky-600" />
                          Nét đứt: phạm vi phát sinh.
                        </span>
                      </>
                    )}
                  </div>

                  {compact && detailMarker ? (
                    <div className="absolute inset-x-0 bottom-0 z-30 max-h-[75%] overflow-y-auto rounded-t-2xl border-t border-slate-300 bg-white p-3 shadow-[0_-8px_24px_rgba(15,23,42,0.18)]">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-slate-500">Chi tiết cấu kiện</p>
                          <h4 className="break-words font-mono text-base font-semibold text-slate-900">
                            {detailMarker.code}
                          </h4>
                        </div>
                        <button
                          type="button"
                          className={`${BUTTON} shrink-0 ${FOCUS_RING}`}
                          onClick={closeDetail}
                        >
                          Đóng
                        </button>
                      </div>
                      <dl className="mt-2 grid grid-cols-[7rem_minmax(0,1fr)] gap-x-2 gap-y-1 text-sm">
                        <dt className="text-slate-600">Công đoạn</dt>
                        <dd className="break-words text-slate-900">
                          {detailMarker.current_stage_name ||
                            detailMarker.current_work ||
                            "Chưa có công đoạn"}
                        </dd>
                        <dt className="text-slate-600">Cập nhật cuối</dt>
                        <dd className="text-slate-900">
                          {detailMarker.last_event_date
                            ? formatShortMapDate(detailMarker.last_event_date)
                            : "Chưa có sự kiện"}
                        </dd>
                        <dt className="text-slate-600">Nghiệm thu</dt>
                        <dd className="text-slate-900">
                          {detailMarker.accepted ? "Đã nghiệm thu" : "Chưa nghiệm thu"}
                        </dd>
                        <dt className="text-slate-600">Thi công</dt>
                        <dd className="text-slate-900">
                          {constructionStatusLabel(detailMarker.construction_status)}
                        </dd>
                      </dl>
                      <div className="mt-3 grid gap-2 min-[375px]:grid-cols-2">
                        <button
                          type="button"
                          className={`${BUTTON} w-full ${FOCUS_RING}`}
                          disabled={!onOpenComponent}
                          onClick={() => onOpenComponent?.(detailMarker.component_id)}
                        >
                          Mở chi tiết
                        </button>
                        <button
                          type="button"
                          className={`${PRIMARY_BUTTON} w-full ${FOCUS_RING}`}
                          disabled={!onRequestProgress}
                          onClick={() =>
                            onRequestProgress?.(
                              detailMarker.component_id,
                              detailMarker.current_stage_definition_id ??
                                detailMarker.current_work_definition_id,
                            )
                          }
                        >
                          Ghi tiến độ
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {detailMarker && !selection && !compact ? (
                <section
                  aria-labelledby={detailHeadingId}
                  className="rounded-xl border border-slate-300 bg-white p-3 shadow-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-slate-500">
                        Chi tiết cấu kiện
                      </p>
                      <h4
                        id={detailHeadingId}
                        ref={detailHeadingRef}
                        tabIndex={-1}
                        className="break-words font-mono text-base font-semibold text-slate-900 focus:outline-none"
                      >
                        {detail?.canonical_code ?? detailMarker.code}
                      </h4>
                      <p className="mt-1 text-xs text-slate-600">
                        {componentTypeLabel(detailMarker.type)} ·{" "}
                        {constructionStatusLabel(
                          detailMarker.construction_status,
                        )}{" "}
                        · {originLabel(detailMarker.origin)}
                      </p>
                    </div>
                    <button
                      type="button"
                      aria-label="Đóng chi tiết cấu kiện"
                      className={`${BUTTON} shrink-0 ${FOCUS_RING}`}
                      onClick={closeDetail}
                    >
                      Đóng
                    </button>
                  </div>

                  {onRequestProgress ? (
                    <button
                      type="button"
                      className={`${PRIMARY_BUTTON} mt-3 w-full ${FOCUS_RING}`}
                      onClick={() => onRequestProgress(detailMarker.component_id, detailMarker.current_work_definition_id)}
                    >
                      Ghi tiến độ theo ngày
                    </button>
                  ) : null}

                  <div className="mt-3 grid gap-2 min-[375px]:grid-cols-2">
                    <button
                      type="button"
                      className={`${BUTTON} w-full ${FOCUS_RING}`}
                      disabled={Boolean(placement)}
                      onClick={() => startOverride(detailMarker)}
                    >
                      Đặt lại vị trí
                    </button>
                    {detailMarker.position_id &&
                    detailMarker.position_status === "DRAFT" ? (
                      <button
                        type="button"
                        className={`${PRIMARY_BUTTON} w-full ${FOCUS_RING}`}
                        disabled={reviewBusyId === detailMarker.component_id}
                        onClick={() => void reviewPosition(detailMarker)}
                      >
                        {reviewBusyId === detailMarker.component_id
                          ? "Đang duyệt…"
                          : "Duyệt vị trí"}
                      </button>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    Đặt lại vị trí sẽ ghi đè vị trí bản vẽ và lưu vết kiểm
                    toán. Chỉ quản lý dự án duyệt được vị trí.
                  </p>

                  {detailState === "loading" ? (
                    <p className="mt-3 text-sm text-slate-600">
                      Đang tải chi tiết cấu kiện…
                    </p>
                  ) : null}

                  {detailState === "error" ? (
                    <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-900">
                      <p role="alert">
                        Không tải được chi tiết cấu kiện: {detailError}
                      </p>
                      <button
                        type="button"
                        className={`${BUTTON} mt-2 ${FOCUS_RING}`}
                        onClick={() => void openDetail(detailMarker)}
                      >
                        Thử lại
                      </button>
                    </div>
                  ) : null}

                  {detailState === "ready" && detail ? (
                    <div className="mt-3 space-y-3">
                      <dl className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-x-2 gap-y-1 text-sm">
                        <dt className="text-slate-600">Mã gốc</dt>
                        <dd className="break-words font-mono text-slate-900">
                          {detail.raw_code || "—"}
                        </dd>
                        <dt className="text-slate-600">Trạng thái duyệt</dt>
                        <dd className="break-words text-slate-900">
                          {verificationLabel(detail.verification)}
                        </dd>
                        <dt className="text-slate-600">Nguồn bản ghi</dt>
                        <dd className="break-words text-slate-900">
                          {recordOriginLabel(detail.record_origin)}
                        </dd>
                        <dt className="text-slate-600">Vị trí bản vẽ</dt>
                        <dd className="break-words text-slate-900">
                          {detailMarker.position_status === "DRAFT"
                            ? "Nháp, chờ duyệt"
                            : detailMarker.position_status === "REVIEWED"
                              ? "Đã duyệt"
                              : "Theo bản vẽ"}
                        </dd>
                        <dt className="text-slate-600">Bí danh</dt>
                        <dd className="break-words text-slate-900">
                          {detail.aliases?.length
                            ? detail.aliases.join(", ")
                            : "—"}
                        </dd>
                      </dl>

                      {detail.design_group ? (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                          <h5 className="text-sm font-semibold text-slate-900">
                            Nhóm thiết kế
                          </h5>
                          <p className="mt-1 break-words text-sm text-slate-800">
                            {detail.design_group.name ?? "—"}
                          </p>
                          <p className="text-xs text-slate-600">
                            {[
                              detail.design_group.drawing
                                ? `Bản vẽ ${detail.design_group.drawing}`
                                : null,
                              detail.design_group.source_page
                                ? `Trang ${detail.design_group.source_page}`
                                : null,
                              detail.design_group.source,
                            ]
                              .filter(Boolean)
                              .join(" · ") || "—"}
                          </p>
                        </div>
                      ) : null}

                      {detail.scopes?.length ? (
                        <div>
                          <h5 className="text-sm font-semibold text-slate-900">
                            Phạm vi sửa chữa
                          </h5>
                          <ul className="mt-1 space-y-1">
                            {detail.scopes.map((scope) => (
                              <li
                                key={scope.id}
                                className="flex min-w-0 flex-wrap items-center gap-1 rounded-lg border border-slate-200 p-2 text-xs text-slate-700"
                              >
                                <span className="font-medium text-slate-900">
                                  {originLabel(scope.kind)} · lần {scope.revision}
                                </span>
                                <span>{verificationLabel(scope.verification)}</span>
                                {scope.approval_reference ? (
                                  <span className="break-words">
                                    · Căn cứ: {scope.approval_reference}
                                  </span>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}

                      {detail.stages?.length ? (
                        <div>
                          <h5 className="text-sm font-semibold text-slate-900">
                            Bước thi công
                          </h5>
                          <ul className="mt-1 space-y-1">
                            {detail.stages.map((stage) => (
                              <li
                                key={stage.id}
                                className="flex min-w-0 flex-wrap items-center justify-between gap-1 rounded-lg border border-slate-200 p-2 text-xs"
                              >
                                <span className="min-w-0 break-words text-slate-800">
                                  {stage.name || stage.code}
                                </span>
                                <StatusChip status={stage.status} />
                                {stage.inference_conflict ? (
                                  <span className="text-amber-800">Cần đối chiếu với bước sau</span>
                                ) : stage.inferred_from_stage_id ? (
                                  <span className="text-slate-600">Suy ra từ bước sau</span>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}

                      {detail.work_links?.length ? (
                        <div>
                          <h5 className="text-sm font-semibold text-slate-900">
                            Dòng danh mục công việc
                          </h5>
                          <ul className="mt-1 space-y-1">
                            {detail.work_links.map((link) => (
                              <li
                                key={`${link.dm_row}-${link.work}`}
                                className="break-words rounded-lg border border-slate-200 p-2 text-xs text-slate-700"
                              >
                                <span className="font-medium text-slate-900">
                                  DM dòng {link.dm_row}
                                </span>{" "}
                                · {link.work || "—"}
                                {link.raw_location
                                  ? ` · ${link.raw_location}`
                                  : ""}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}

                      <p className="break-words text-xs text-slate-500">
                        Nguồn: {shortSha(detail.source?.sha256)}
                        {detail.source?.sheet
                          ? ` · ${detail.source.sheet}`
                          : ""}
                        {detail.source?.row
                          ? ` · dòng ${detail.source.row}`
                          : ""}
                      </p>
                    </div>
                  ) : null}
                </section>
              ) : null}

              {!compact ? (
              <details
                className="rounded-xl border border-slate-200 bg-white shadow-sm"
                open
              >
                <summary
                  className={`flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 p-3 text-sm font-semibold text-slate-900 [&::-webkit-details-marker]:hidden ${FOCUS_RING}`}
                >
                  <span>Danh sách cấu kiện ({visibleMarkerCount})</span>
                  <span aria-hidden="true" className="text-slate-500">
                    ⌄
                  </span>
                </summary>
                <div className="divide-y divide-slate-200 border-t border-slate-200">
                  {filteredSheets.map((sheet) => (
                    <section key={sheet.id} className="p-3">
                      <h5 className="break-words text-sm font-semibold text-slate-900">
                        {sheet.title}
                      </h5>
                      <p className="mt-0.5 text-xs text-slate-600">
                        Bản vẽ {sheet.drawing} · trang {sheet.page}
                      </p>
                      {sheet.markers.length ? (
                        <ul className="mt-2 space-y-1">
                          {sheet.markers.map((marker) => (
                            <li
                              key={`${marker.component_id}-${marker.code}`}
                            >
                              <button
                                type="button"
                                className={`flex min-h-11 w-full min-w-0 flex-wrap items-center justify-between gap-1 rounded-lg border border-slate-200 px-2 py-1 text-left text-sm text-slate-800 active:bg-slate-50 ${FOCUS_RING}`}
                                onClick={() => void openDetail(marker)}
                              >
                                <span className="break-words font-mono font-semibold text-slate-900">
                                  {marker.code}
                                </span>
                                <span className="break-words text-xs text-slate-600">
                                  {componentTypeLabel(marker.type)} ·{" "}
                                  {constructionStatusLabel(
                                    marker.construction_status,
                                  )}{" "}
                                  · {originLabel(marker.origin)}
                                </span>
                              </button>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-2 text-xs text-slate-500">
                          Chưa gắn cấu kiện trên trang này.
                        </p>
                      )}
                    </section>
                  ))}
                </div>
              </details>
              ) : null}
            </>
          )}
        </>
      ) : null}
    </section>
  );
}
