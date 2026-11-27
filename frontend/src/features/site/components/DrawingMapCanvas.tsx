/** Interactive drawing sheet canvas: image, marker overlay and placement points. */

import { useEffect, type ReactNode } from "react";
import {
  ACCEPTANCE_OUTLINE_COLOR,
  constructionStatusColor,
  viewTransform,
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
  type VisibleLabel,
} from "../lib/drawingMapPanel";
import DrawingMapViewControls from "./DrawingMapViewControls";
import SchematicPlanSurface from "./SchematicPlanSurface";
import type { ImageState } from "./useDrawingMapResources";

export type HitChoices = {
  x: number;
  y: number;
  markers: DrawingMarker[];
  flip: boolean;
};

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
  contentRef: React.RefObject<HTMLDivElement | null>;
  imageRef: React.RefObject<HTMLImageElement | null>;
  view: View;
  imageBox: ImageBox | null;
  mapTargets: MapTarget[];
  labels: VisibleLabel[];
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
  hitChoices: HitChoices | null;
  onChooseHit: (marker: DrawingMarker) => void;
  onDismissHit: () => void;
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
  contentRef,
  imageRef,
  view,
  imageBox,
  mapTargets,
  labels,
  selection,
  detailMarker,
  placement,
  dragPointIndex,
  setDragPointIndex,
  updatePlacementPoint,
  onImageLoad,
  onMarkerActivate,
  hitChoices,
  onChooseHit,
  onDismissHit,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onPointerCancel,
  zoomBy,
  resetView,
  showWholeSheet,
  children,
}: Props) {
  useEffect(() => {
    const element = contentRef.current;
    if (!element) return;
    element.style.transform = viewTransform(view);
  }, [contentRef, view]);

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      {!compact ? (
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-200 p-3">
          <div className="min-w-0">
            <h4 className="break-words text-sm font-semibold text-slate-900">
              {activeSheet.title}
            </h4>
            <p className="mt-0.5 text-xs text-slate-600">
              {activeSheet.schematic
                ? `Sơ đồ theo mã cấu kiện · ${activeSheet.markers.length} vị trí`
                : `Bản vẽ ${activeSheet.drawing} · trang ${activeSheet.page} · ${activeSheet.markers.length} vị trí`}
            </p>
          </div>
        </div>
      ) : null}

      <div
        ref={viewportRef}
        className={`relative w-full touch-none select-none overflow-hidden bg-slate-100 ${
          compact
            ? "min-h-[45vh] max-h-[65vh]"
            : "h-[62vh] min-h-64 max-h-[38rem]"
        }`}
        style={
          compact && !activeSheet.schematic
            ? { aspectRatio: compactAspect }
            : undefined
        }
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
            Đang tải mặt bằng…
          </p>
        ) : null}

        {imageState === "error" ? (
          <div className="absolute inset-0 grid place-items-center p-4 text-center">
            <div className="max-w-sm">
              <p role="alert" className="text-sm text-red-900">
                Không tải được mặt bằng: {imageError}
              </p>
              <button
                type="button"
                className={`${BUTTON} mt-3 ${FOCUS_RING}`}
                onClick={retryImage}
              >
                Thử lại
              </button>
            </div>
          </div>
        ) : null}

        {imageState === "ready" && (imageUrl || activeSheet.schematic) ? (
          <div
            ref={contentRef}
            className="absolute inset-0 will-change-transform"
          >
            {imageUrl ? (
              <img
                ref={imageRef}
                src={imageUrl}
                alt={`Bản vẽ ${activeSheet.drawing}, trang ${activeSheet.page}`}
                className="h-full w-full object-contain"
                draggable={false}
                onLoad={onImageLoad}
              />
            ) : null}
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
                {activeSheet.schematic ? (
                  <SchematicPlanSurface
                    plan={activeSheet.schematic}
                    box={{
                      left: 0,
                      top: 0,
                      width: imageBox.width,
                      height: imageBox.height,
                    }}
                  />
                ) : null}
                <svg
                  role="group"
                  aria-label="Cấu kiện trên bản vẽ"
                  focusable="false"
                  viewBox="0 0 1 1"
                  preserveAspectRatio="none"
                  className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
                >
                  {mapTargets.map(({ marker, points, x, y }) => {
                    const selected = selection
                      ? selection.selectedIds.includes(marker.component_id)
                      : detailMarker?.component_id === marker.component_id;
                    const selectable =
                      !selection ||
                      selection.selectableIds.includes(marker.component_id);
                    const opacity = selection && !selectable ? 0.2 : 1;
                    const color = markerStrokeColor(marker, compact);
                    const accepted = Boolean(marker.accepted);
                    const isCorner = /^Q-\d+$/i.test(marker.code);
                    const isFender = /^K-/i.test(marker.code);
                    const unitX = (pixels: number) =>
                      pixels / Math.max(1, imageBox.width * view.zoom);
                    const unitY = (pixels: number) =>
                      pixels / Math.max(1, imageBox.height * view.zoom);
                    const statusColor = constructionStatusColor(
                      marker.construction_status,
                    );
                    const path = points.map(([px, py]) => `${px},${py}`).join(" ");
                    return (
                      <g
                        key={`${marker.component_id}-${marker.code}`}
                        role="button"
                        tabIndex={0}
                        focusable="true"
                        aria-label={markerAriaLabel(marker, {
                          selecting: Boolean(selection),
                          selected,
                          selectable,
                        })}
                        aria-pressed={selected}
                        className="outline-none"
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            onMarkerActivate(marker);
                          }
                        }}
                      >
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
                              strokeWidth={
                                selected
                                  ? marker.type === "beam"
                                    ? 5
                                    : 2.5
                                  : marker.type === "beam"
                                    ? 3.5
                                    : 1.5
                              }
                              strokeLinecap="round" strokeLinejoin="round"
                              strokeDasharray={markerDashArray(marker, "line")}
                              opacity={opacity}
                              vectorEffect="non-scaling-stroke" />
                          </>
                        ) : isCorner ? (
                          <g transform={`rotate(45 ${x} ${y})`}>
                            {accepted ? (
                              <rect
                                x={x - unitX(8)}
                                y={y - unitY(8)}
                                width={unitX(16)}
                                height={unitY(16)}
                                fill="none"
                                stroke={ACCEPTANCE_OUTLINE_COLOR}
                                strokeWidth={selected ? 3 : 2}
                                opacity={opacity}
                                vectorEffect="non-scaling-stroke"
                              />
                            ) : null}
                            <rect
                              x={x - unitX(5)}
                              y={y - unitY(5)}
                              width={unitX(10)}
                              height={unitY(10)}
                              fill={selected ? "#111827" : statusColor}
                              opacity={opacity}
                            />
                          </g>
                        ) : isFender ? (
                          <>
                            {accepted ? (
                              <rect
                                x={x - unitX(7)}
                                y={y - unitY(5)}
                                width={unitX(14)}
                                height={unitY(10)}
                                fill="none"
                                stroke={ACCEPTANCE_OUTLINE_COLOR}
                                strokeWidth={selected ? 3 : 2}
                                opacity={opacity}
                                vectorEffect="non-scaling-stroke"
                              />
                            ) : null}
                            <rect
                              x={x - unitX(5)}
                              y={y - unitY(3)}
                              width={unitX(10)}
                              height={unitY(6)}
                              fill={selected ? "#111827" : statusColor}
                              opacity={opacity}
                            />
                          </>
                        ) : (
                          <>
                            {accepted ? (
                              <ellipse
                                cx={x}
                                cy={y}
                                rx={unitX(7.5)}
                                ry={unitY(7.5)}
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
                              rx={unitX(5)}
                              ry={unitY(5)}
                              fill={selected ? "#111827" : statusColor}
                              opacity={opacity}
                            />
                          </>
                        )}
                      </g>
                    );
                  })}
                </svg>

                {placement &&
                placement.sheetId === activeSheet?.id &&
                placement.points.length > 1 ? (
                  <svg
                    aria-hidden="true"
                    focusable="false"
                    viewBox="0 0 1 1"
                    preserveAspectRatio="none"
                    className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
                  >
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
                  </svg>
                ) : null}

                {labels.map(({ target, text, fontPx, status }) => (
                  <span
                    key={`label-${target.marker.component_id}-${target.marker.code}`}
                    aria-hidden="true"
                    className="pointer-events-none absolute z-[5] whitespace-nowrap font-semibold"
                    style={{
                      left: `${target.x * 100}%`,
                      top: `${target.y * 100}%`,
                      transform: "translateX(-50%)",
                      marginTop: (fontPx + 4) / view.zoom,
                      fontSize: fontPx / view.zoom,
                      lineHeight: 1.1,
                      color: constructionStatusColor(status),
                      textShadow:
                        "0 0 2px #fff, 0 0 2px #fff, 0 0 3px #fff, 0 0 4px #fff",
                    }}
                  >
                    {text}
                  </span>
                ))}

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

        {hitChoices ? (
          <div
            role="listbox"
            aria-label="Chọn cấu kiện tại điểm chạm"
            className="absolute z-30 w-56 max-w-[85%] rounded-xl border border-slate-300 bg-white p-1.5 shadow-xl"
            style={{
              left: hitChoices.x,
              top: hitChoices.y + (hitChoices.flip ? -12 : 12),
              transform: hitChoices.flip
                ? "translate(-50%, -100%)"
                : "translate(-50%, 0)",
            }}
            onPointerDown={(event) => event.stopPropagation()}
          >
            <p className="px-2 py-1 text-xs font-semibold text-slate-500">
              Chọn cấu kiện
            </p>
            <ul className="max-h-52 overflow-y-auto">
              {hitChoices.markers.map((marker) => (
                <li key={marker.component_id}>
                  <button
                    type="button"
                    className={`flex min-h-10 w-full items-center justify-between gap-2 rounded-lg px-2 text-left text-sm text-slate-800 active:bg-slate-100 ${FOCUS_RING}`}
                    onClick={() => onChooseHit(marker)}
                  >
                    <span className="font-mono font-semibold">
                      {marker.code}
                    </span>
                    <span className="text-xs text-slate-500">
                      {marker.type === "pile" ? "Cọc" : "Dầm"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="mt-1 min-h-9 w-full rounded-lg px-2 text-xs font-medium text-slate-500 active:bg-slate-100"
              onClick={onDismissHit}
            >
              Đóng
            </button>
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
