/** Pure helpers and shared class tokens for the drawing map panel. */

import { ApiError } from "./api";
import {
  componentTypeLabel,
  constructionStatusLabel,
  constructionStatusColor,
  designGroupColor,
  isAdditionalScope,
  originLabel,
  sanitizePoints,
  type DrawingFilters,
  type DrawingMarker,
  type MarkerBounds,
} from "./drawingMap";

export type PlacementTarget = {
  componentId: string;
  code: string;
  type: "pile" | "beam";
};

export type Selection = {
  selectedIds: string[];
  selectableIds: string[];
  disabled?: boolean;
  onToggle: (componentId: string) => void;
};

export type Placement = PlacementTarget & {
  sheetId: string;
  points: Array<[number, number]>;
  override: boolean;
};

export type MapTarget = {
  marker: DrawingMarker;
  points: Array<[number, number]>;
  x: number;
  y: number;
};

export const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-700 focus-visible:ring-offset-2";

export const FIELD =
  "mt-1 min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300 sm:text-sm";

export const BUTTON =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 active:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400";

export const PRIMARY_BUTTON =
  "min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-semibold text-white active:bg-slate-900 disabled:bg-slate-300";

const STATUS_CHIP: Record<string, string> = {
  NOT_STARTED: "app-status app-status--not-started",
  IN_PROGRESS: "app-status app-status--in-progress",
  COMPLETED: "app-status app-status--completed",
  BLOCKED: "app-status app-status--blocked",
};

export function statusChipClass(status: string): string {
  return STATUS_CHIP[status] ?? "app-status app-status--not-started";
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Không xác định được lỗi.";
}

export function isPending(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.status === 404 || error.status === 405 || error.status === 501)
  );
}

export function formatShortMapDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value;
}

export function verificationLabel(value: string): string {
  if (value === "VERIFIED") return "Đã duyệt";
  if (value === "NEEDS_REVIEW") return "Chờ duyệt";
  return value;
}

export function recordOriginLabel(value: string): string {
  if (value === "SEED_IMPORT") return "Nhập từ danh mục";
  if (value === "MANUAL_ENTRY") return "Nhập thủ công";
  return value;
}

export function shortSha(value?: string | null): string {
  return value ? `${value.slice(0, 12)}…` : "—";
}

export function markerLabel(marker: DrawingMarker): string {
  return [
    marker.code,
    componentTypeLabel(marker.type),
    constructionStatusLabel(marker.construction_status),
    originLabel(marker.origin),
  ].join(" · ");
}

export function hasActiveFilters(filters: DrawingFilters): boolean {
  return Boolean(
    filters.query.trim() ||
      filters.type ||
      filters.status ||
      filters.origin,
  );
}

/** Middle point of each marker so piles get one dot and beams get a midpoint. */
export function buildMapTargets(
  markers: ReadonlyArray<DrawingMarker>,
): MapTarget[] {
  return markers
    .flatMap((marker) => {
      const points = sanitizePoints(marker.points);
      if (!points.length) return [];
      const middle = Math.floor((points.length - 1) / 2);
      const [x, y] = points[middle];
      const [endX, endY] = points[middle + 1] ?? points[middle];
      return [{ marker, points, x: (x + endX) / 2, y: (y + endY) / 2 }];
    })
    .sort(
      (a, b) => Number(a.points.length === 1) - Number(b.points.length === 1),
    );
}

export function markerStrokeColor(
  marker: DrawingMarker,
  compact: boolean,
): string {
  if (compact) return constructionStatusColor(marker.construction_status);
  return (
    designGroupColor(marker.design_group) ??
    (marker.type === "beam" ? "#0f766e" : "#0369a1")
  );
}

/** Dashed styles for pending review and additional-scope markers. */
export function markerDashArray(
  marker: DrawingMarker,
  shape: "line" | "point",
): string | undefined {
  if (marker.location_review || marker.position_status === "DRAFT") {
    return shape === "line" ? "2 3" : "1.5 2";
  }
  if (isAdditionalScope(marker)) return shape === "line" ? "5 3" : "2 2";
  return undefined;
}

export function markerAriaLabel(
  marker: DrawingMarker,
  options: { selecting: boolean; selected?: boolean; selectable?: boolean },
): string {
  const label = markerLabel(marker);
  if (options.selecting) {
    return `${options.selected ? "Bỏ chọn" : "Chọn"} ${label}${options.selectable ? "" : ", không phù hợp công việc"}`;
  }
  return `Mở chi tiết ${label}${marker.current_work ? `, đang làm ${marker.current_work}` : ""}`;
}

export function pointerDistance(
  a: { x: number; y: number },
  b: { x: number; y: number },
): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

export function placementSaveError(placement: Placement): string | null {
  if (placement.type === "pile" && placement.points.length !== 1) {
    return "Cọc cần đúng một điểm trên bản vẽ.";
  }
  if (placement.type === "beam" && placement.points.length < 2) {
    return "Dầm cần ít nhất hai điểm để vẽ đường tim.";
  }
  return null;
}

export function nextPlacementPoints(
  placement: Placement,
  point: [number, number],
): Array<[number, number]> {
  if (placement.type === "pile") return [point];
  if (placement.points.length >= 30) return placement.points;
  return [...placement.points, point];
}

/**
 * Viewport aspect (width / height) for the compact overview card. Match the
 * marker bounding box so fitting the map does not leave a large empty band
 * under the drawing; fall back to the sheet aspect for empty/degenerate boxes.
 * Clamped so one collinear beam cannot turn the card into a strip.
 */
export function contentAspectRatio(
  bounds: MarkerBounds | null,
  imageAspect: number | null | undefined,
  fallback = 1.4,
): number {
  const sheet =
    imageAspect && Number.isFinite(imageAspect) && imageAspect > 0
      ? imageAspect
      : fallback;
  if (!bounds) return sheet;
  const width = bounds.maxX - bounds.minX;
  const height = bounds.maxY - bounds.minY;
  if (!(width > 0) && !(height > 0)) return sheet;
  const ratio =
    (Math.max(width, 0.02) / Math.max(height, 0.02)) * sheet;
  if (!Number.isFinite(ratio) || ratio <= 0) return sheet;
  return Math.min(3, Math.max(0.5, ratio));
}
