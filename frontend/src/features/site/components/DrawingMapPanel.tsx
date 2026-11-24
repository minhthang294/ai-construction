import { useMemo, useRef } from "react";
import { containBox, markerBounds, type DrawingMarker } from "../lib/drawingMap";
import {
  BUTTON,
  FOCUS_RING,
  buildMapTargets,
  contentAspectRatio,
  type PlacementTarget,
  type Selection,
} from "../lib/drawingMapPanel";
import DrawingMapCanvas from "./DrawingMapCanvas";
import DrawingMapComponentList from "./DrawingMapComponentList";
import DrawingMapDetailPanel, {
  DrawingMapCompactDetail,
} from "./DrawingMapDetailPanel";
import DrawingMapFilters from "./DrawingMapFilters";
import DrawingMapPlacementPanel from "./DrawingMapPlacementPanel";
import DrawingMapSheetTabs from "./DrawingMapSheetTabs";
import { useDrawingMapDetail } from "./useDrawingMapDetail";
import { useDrawingMapGestures } from "./useDrawingMapGestures";
import { useDrawingMapPlacement } from "./useDrawingMapPlacement";
import { useDrawingMapResources } from "./useDrawingMapResources";
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
  const imageRef = useRef<HTMLImageElement>(null);

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
    activeImageUrl,
    imageInView,
    imageUrl,
    imageState,
    imageError,
    imageReloadKey,
    retryImage,
    imageBox,
    setImageBox,
  } = useDrawingMapResources({
    projectId,
    batchId,
    compact,
    primaryZone,
    refreshKey,
    lazyReady,
    rootRef,
    imageRef,
  });

  const {
    view,
    setView,
    viewRef,
    zoomBy,
    resetView,
    showWholeSheet,
  } = useDrawingMapViewport({
    activeImageUrl,
    imageReloadKey,
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

  const {
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
  } = useDrawingMapPlacement({
    projectId,
    activeSheetId: activeSheet?.id ?? "",
    placementRequest,
    onPlacementDone,
    closeDetail,
    setDetailMarker,
    retryLoad,
    viewportRef,
    imageBox,
    viewRef,
  });

  const { handlePointerDown, handlePointerMove, endPointer } =
    useDrawingMapGestures({
      viewRef,
      viewportRef,
      setView,
      placementActive: Boolean(placement),
      addPlacementPoint,
    });

  const mapTargets = useMemo(
    () => buildMapTargets(activeSheet?.markers ?? []),
    [activeSheet],
  );
  const compactAspect = useMemo(
    () =>
      contentAspectRatio(
        markerBounds(activeSheet?.markers ?? []),
        imageBox ? imageBox.width / imageBox.height : null,
      ),
    [activeSheet, imageBox],
  );
  const reviewCount = map?.review_count ?? 0;

  function handleImageLoad() {
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
  }

  function handleMarkerActivate(marker: DrawingMarker) {
    if (selection) {
      selection.onToggle(marker.component_id);
      return;
    }
    void openDetail(marker);
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
        <DrawingMapPlacementPanel
          placement={placement}
          activeSheet={activeSheet}
          placementBusy={placementBusy}
          placementError={placementError}
          savePlacement={savePlacement}
          cancelPlacement={cancelPlacement}
          removeLastPlacementPoint={removeLastPlacementPoint}
        />
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
                  placement={placement}
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
                  imageUrl={imageUrl}
                  viewportRef={viewportRef}
                  imageRef={imageRef}
                  view={view}
                  imageBox={imageBox}
                  mapTargets={mapTargets}
                  selection={selection}
                  detailMarker={detailMarker}
                  placement={placement}
                  dragPointIndex={dragPointIndex}
                  setDragPointIndex={setDragPointIndex}
                  updatePlacementPoint={updatePlacementPoint}
                  onImageLoad={handleImageLoad}
                  onMarkerActivate={handleMarkerActivate}
                  onPointerDown={handlePointerDown}
                  onPointerMove={handlePointerMove}
                  onPointerUp={endPointer}
                  onPointerCancel={endPointer}
                  zoomBy={zoomBy}
                  resetView={resetView}
                  showWholeSheet={showWholeSheet}
                >
                  {compact && detailMarker ? (
                    <DrawingMapCompactDetail
                      detailMarker={detailMarker}
                      closeDetail={closeDetail}
                      onOpenComponent={onOpenComponent}
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
                  startOverride={startOverride}
                  reviewPosition={reviewPosition}
                  reviewBusyId={reviewBusyId}
                  placement={placement}
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
    </section>
  );
}
