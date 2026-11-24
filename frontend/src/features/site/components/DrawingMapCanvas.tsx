/** Interactive drawing sheet canvas: image, marker overlay and placement points. */

import type { ReactNode } from "react";
import {
  ACCEPTANCE_OUTLINE_COLOR,
  type DrawingMarker,
  type DrawingSheet,
  type ImageBox,
  type View,
} from "../lib/drawingMap";
import {
  BUTTON,
  FOCUS_RING,
  markerAriaLabel,
  markerDashArray,
  markerStrokeColor,
  type MapTarget,
  type Placement,
  type Selection,
} from "../lib/drawingMapPanel";
import DrawingMapViewControls from "./DrawingMapViewControls";
import type { ImageState } from "./useDrawingMapResources";

type Props = {
  activeSheet: DrawingSheet;
  compact: boolean;
  /** Compact viewport width/height; derived from the fitted marker box. */
  compactAspect: number;
  imageInView: boolean;
  imageState: ImageState;
  imageError: string | null;
  retryImage: () => void;
  imageUrl: string | null;
  viewportRef: React.RefObject<HTMLDivElement | null>;
  imageRef: React.RefObject<HTMLImageElement | null>;
  view: View;
  imageBox: ImageBox | null;
  mapTargets: MapTarget[];
  selection?: Selection;
  detailMarker: DrawingMarker | null;
  placement: Placement | null;
  dragPointIndex: number | null;
  setDragPointIndex: (index: number | null) => void;
  updatePlacementPoint: (
    index: number,
    event: { clientX: number; clientY: number },
  ) => void;
  onImageLoad: () => void;
  onMarkerActivate: (marker: DrawingMarker) => void;
  onPointerDown: (event: React.PointerEvent<HTMLDivElement>) => void;
  onPointerMove: (event: React.PointerEvent<HTMLDivElement>) => void;
  onPointerUp: (event: React.PointerEvent<HTMLDivElement>) => void;
  onPointerCancel: (event: React.PointerEvent<HTMLDivElement>) => void;
  zoomBy: (delta: number) => void;
  resetView: () => void;
  showWholeSheet: () => void;
  children?: ReactNode;
};

export default function DrawingMapCanvas({
  activeSheet,
  compact,
  compactAspect,
  imageInView,
  imageState,
  imageError,
  retryImage,
  imageUrl,
  viewportRef,
  imageRef,
  view,
  imageBox,
  mapTargets,
  selection,
  detailMarker,
  placement,
  dragPointIndex,
  setDragPointIndex,
  updatePlacementPoint,
  onImageLoad,
  onMarkerActivate,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onPointerCancel,
  zoomBy,
  resetView,
  showWholeSheet,
  children,
}: Props) {
  return (
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
            ? "min-h-[45vh] max-h-[65vh]"
            : "h-[62vh] min-h-64 max-h-[38rem]"
        }`}
        style={compact ? { aspectRatio: compactAspect } : undefined}
        role="group"
        aria-label="Bản đồ bản vẽ tương tác"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
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
                onClick={retryImage}
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
              onLoad={onImageLoad}
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
                    const color = markerStrokeColor(marker, compact);
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
                              strokeDasharray={markerDashArray(marker, "line")}
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
                              strokeDasharray={markerDashArray(marker, "point")}
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
                      aria-label={markerAriaLabel(marker, {
                        selecting: Boolean(selection),
                        selected,
                        selectable,
                      })}
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
                      onClick={() => onMarkerActivate(marker)}
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

      <DrawingMapViewControls
        compact={compact}
        view={view}
        zoomBy={zoomBy}
        resetView={resetView}
        showWholeSheet={showWholeSheet}
      />

      {children}
    </div>
  );
}
