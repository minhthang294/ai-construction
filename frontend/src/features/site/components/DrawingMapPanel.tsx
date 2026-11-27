import { useEffect, useMemo, useRef, useState } from "react";
import {
  containBox,
  fetchDrawingMap,
  fetchDrawingSheetImageUrl,
  markerBounds,
  sheetToClient,
  type DrawingMarker,
} from "../lib/drawingMap";
import {
  BUTTON,
  FOCUS_RING,
  buildMapTargets,
  contentAspectRatio,
  hitTestMarkers,
  labelModeForZoom,
  layoutMarkerLabels,
  type PlacementTarget,
  type ScreenTarget,
  type Selection,
} from "../lib/drawingMapPanel";
import DrawingMapCanvas, { type HitChoices } from "./DrawingMapCanvas";
import DrawingMapComponentList from "./DrawingMapComponentList";
import DrawingMapDetailPanel, {
  DrawingMapCompactDetail,
} from "./DrawingMapDetailPanel";
import DrawingMapFilters from "./DrawingMapFilters";
import DrawingMapSheetTabs from "./DrawingMapSheetTabs";
import { useDrawingMapDetail } from "./useDrawingMapDetail";
import { useDrawingMapGestures } from "./useDrawingMapGestures";
import { useSchematicMapResources } from "./useSchematicMapResources";
import { useDrawingMapViewport } from "./useDrawingMapViewport";

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

export type { PlacementTarget };

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
  const viewportRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [hitChoices, setHitChoices] = useState<HitChoices | null>(null);
  const [originalState, setOriginalState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [originalUrl, setOriginalUrl] = useState<string | null>(null);

  const {
    map,
    loadState,
    loadError,
    retryLoad,
    filters,
    updateFilter,
    clearFilters,
    hasFilters,
    filteredSheets,
    activeSheet,
    setActiveSheetId,
    visibleMarkerCount,
    allMarkerCount,
    activeSheetKey,
    imageInView,
    imageState,
    imageError,
    retryImage,
    imageBox,
    setImageBox,
  } = useSchematicMapResources({
    projectId,
    batchId,
    compact,
    primaryZone,
    refreshKey,
    lazyReady,
  });

  const {
    view,
    setView,
    viewRef,
    zoomBy,
    resetView,
    showWholeSheet,
    markUserInteraction,
  } = useDrawingMapViewport({
    activeSheetKey,
    activeSheet,
    imageState,
    imageBox,
    viewportRef,
  });

  const {
    detailMarker,
    setDetailMarker,
    detail: componentDetail,
    detailState,
    detailError,
    detailHeadingRef,
    detailHeadingId,
    openDetail,
    closeDetail,
  } = useDrawingMapDetail({ projectId, compact });

  const { handlePointerDown, handlePointerMove, endPointer, cancelPointer } =
    useDrawingMapGestures({
      viewRef,
      viewportRef,
      contentRef,
      setView,
      placementActive: false,
      addPlacementPoint: () => undefined,
      onTap: handleMapTap,
      onUserInteraction: markUserInteraction,
    });

  const mapTargets = useMemo(
    () => buildMapTargets(activeSheet?.markers ?? []),
    [activeSheet],
  );
  const compactAspect = useMemo(
    () =>
      activeSheet?.schematic
        ? activeSheet.schematic.width / activeSheet.schematic.height
        : contentAspectRatio(
            markerBounds(activeSheet?.markers ?? []),
            imageBox ? imageBox.width / imageBox.height : null,
          ),
    [activeSheet, imageBox],
  );
  const labels = useMemo(
    () =>
      imageBox
        ? layoutMarkerLabels(
            mapTargets,
            labelModeForZoom(view.zoom),
            view.zoom,
            imageBox,
          )
        : [],
    [imageBox, mapTargets, view.zoom],
  );
  const reviewCount = map?.review_count ?? 0;

  useEffect(() => {
    setHitChoices(null);
  }, [activeSheetKey, imageBox]);

  useEffect(() => {
    const plan = activeSheet?.schematic;
    const viewport = viewportRef.current;
    if (!plan || !viewport) return;
    const update = () => {
      // Keep the plan's aspect ratio; stretching to the viewport distorts text.
      setImageBox(
        containBox(plan.width, plan.height, viewport.clientWidth, viewport.clientHeight),
      );
    };
    update();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(update);
    observer.observe(viewport);
    return () => observer.disconnect();
  }, [activeSheet, setImageBox]);

  function handleMarkerActivate(marker: DrawingMarker) {
    setHitChoices(null);
    if (selection) {
      if (
        selection.disabled ||
        !selection.selectableIds.includes(marker.component_id)
      ) {
        return;
      }
      selection.onToggle(marker.component_id);
      return;
    }
    void openDetail(marker);
  }

  async function openOriginal() {
    setOriginalState("loading");
    try {
      const fullMap = await fetchDrawingMap(projectId, batchId);
      const containing = fullMap.sheets.find((sheet) =>
        sheet.markers.some(
          (marker) => marker.component_id === detailMarker?.component_id,
        ),
      );
      const sheet = containing ?? fullMap.sheets[0];
      if (!sheet) throw new Error("Không có bản vẽ gốc.");
      const url = await fetchDrawingSheetImageUrl(sheet.image_url);
      setOriginalUrl(url);
      setOriginalState("ready");
    } catch {
      setOriginalState("error");
    }
  }

  function closeOriginal() {
    if (originalUrl) URL.revokeObjectURL(originalUrl);
    setOriginalUrl(null);
    setOriginalState("idle");
  }

  function handleMapTap(clientX: number, clientY: number) {
    const viewport = viewportRef.current;
    if (!viewport || !imageBox) return;
    const rect = viewport.getBoundingClientRect();
    const current = viewRef.current;
    const availableTargets =
      selection && !selection.disabled
        ? mapTargets.filter((target) =>
            selection.selectableIds.includes(target.marker.component_id),
          )
        : selection
          ? []
          : mapTargets;
    const targets: ScreenTarget[] = availableTargets.map((target) => ({
      marker: target.marker,
      points: target.points.map((point) =>
        sheetToClient(point, rect, imageBox, current),
      ),
    }));
    const hits = hitTestMarkers(targets, [clientX, clientY]);
    if (!hits.length) {
      setHitChoices(null);
      return;
    }
    if (hits.length === 1) {
      handleMarkerActivate(hits[0].marker);
      return;
    }
    const x = Math.min(
      Math.max(clientX - rect.left, 112),
      Math.max(112, rect.width - 112),
    );
    const y = clientY - rect.top;
    setHitChoices({
      x,
      y,
      markers: hits.map((hit) => hit.marker),
      flip: y > rect.height * 0.55,
    });
  }

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
            onClick={retryLoad}
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
            onClick={retryLoad}
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
            <DrawingMapFilters
              filters={filters}
              updateFilter={updateFilter}
              visibleMarkerCount={visibleMarkerCount}
              hasFilters={hasFilters}
              clearFilters={clearFilters}
            />
          ) : null}

          {filteredSheets.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
              Không có cấu kiện khớp bộ lọc.
            </div>
          ) : (
            <>
              {!compact || filteredSheets.length > 1 ? (
                <DrawingMapSheetTabs
                  filteredSheets={filteredSheets}
                  activeSheet={activeSheet}
                  placement={null}
                  setActiveSheetId={setActiveSheetId}
                />
              ) : null}

              {activeSheet ? (
                <DrawingMapCanvas
                  activeSheet={activeSheet}
                  compact={compact}
                  compactAspect={compactAspect}
                  imageInView={imageInView}
                  imageState={imageState}
                  imageError={imageError}
                  retryImage={retryImage}
                  imageUrl={null}
                  viewportRef={viewportRef}
                  contentRef={contentRef}
                  imageRef={imageRef}
                  view={view}
                  imageBox={imageBox}
                  mapTargets={mapTargets}
                  labels={labels}
                  selection={selection}
                  detailMarker={detailMarker}
                  placement={null}
                  dragPointIndex={null}
                  setDragPointIndex={() => undefined}
                  updatePlacementPoint={() => undefined}
                  onImageLoad={() => undefined}
                  onMarkerActivate={handleMarkerActivate}
                  hitChoices={hitChoices}
                  onChooseHit={handleMarkerActivate}
                  onDismissHit={() => setHitChoices(null)}
                  onPointerDown={handlePointerDown}
                  onPointerMove={handlePointerMove}
                  onPointerUp={endPointer}
                  onPointerCancel={cancelPointer}
                  zoomBy={zoomBy}
                  resetView={resetView}
                  showWholeSheet={showWholeSheet}
                >
                  {compact && detailMarker ? (
                    <DrawingMapCompactDetail
                      detailMarker={detailMarker}
                      closeDetail={closeDetail}
                      onOpenComponent={onOpenComponent}
                      onOpenOriginal={() => void openOriginal()}
                      onRequestProgress={onRequestProgress}
                    />
                  ) : null}
                </DrawingMapCanvas>
              ) : null}

              {detailMarker && !selection && !compact ? (
                <DrawingMapDetailPanel
                  detailMarker={detailMarker}
                  detail={componentDetail}
                  detailState={detailState}
                  detailError={detailError}
                  openDetail={openDetail}
                  closeDetail={closeDetail}
                  onOpenOriginal={() => void openOriginal()}
                  onRequestProgress={onRequestProgress}
                  detailHeadingId={detailHeadingId}
                  detailHeadingRef={detailHeadingRef}
                />
              ) : null}

              {!compact ? (
                <DrawingMapComponentList
                  filteredSheets={filteredSheets}
                  visibleMarkerCount={visibleMarkerCount}
                  openDetail={openDetail}
                />
              ) : null}
            </>
          )}
        </>
      ) : null}
      {originalState !== "idle" ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Bản vẽ gốc"
          className="fixed inset-0 z-50 flex flex-col bg-slate-950/80 p-3"
        >
          <div className="mb-2 flex justify-end">
            <button
              type="button"
              className={`${BUTTON} ${FOCUS_RING}`}
              onClick={closeOriginal}
            >
              Đóng bản vẽ gốc
            </button>
          </div>
          <div className="grid min-h-0 flex-1 place-items-center overflow-auto rounded-xl bg-white p-2">
            {originalState === "loading" ? (
              <p className="text-sm text-slate-600">Đang tải bản vẽ gốc…</p>
            ) : originalState === "error" ? (
              <p role="alert" className="text-sm text-red-800">
                Không tải được bản vẽ gốc cho cấu kiện này.
              </p>
            ) : originalUrl ? (
              <img
                src={originalUrl}
                alt="Bản vẽ gốc"
                className="max-h-full max-w-full object-contain"
              />
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
