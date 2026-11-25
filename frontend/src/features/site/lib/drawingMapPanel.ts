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

const WORK_ALIASES: Array<[RegExp, string]> = [
  [/đục\s*(bt|bê\s*tông)/i, "Đục BT"],
  [/tẩy\s*gỉ/i, "Tẩy gỉ"],
  [/vệ\s*sinh/i, "Vệ sinh"],
  [/epoxy/i, "Epoxy"],
  [/cát\s*nhám/i, "Cát nhám"],
  [/ván\s*khuôn/i, "Ván khuôn"],
  [/vữa\s*kcn/i, "Vữa KCN"],
  [/sợi\s*tt/i, "Sợi TT L1"],
  [/sơn\s*uv/i, "Sơn UV"],
  [/đổ\s*thải/i, "Đổ thải"],
];

/** Short Vietnamese work label; fallback is the first three meaningful words. */
export function abbreviateWorkName(value: string | null | undefined): string | null {
  const normalized = (value ?? "").replace(/\s+/g, " ").trim();
  if (!normalized) return null;
  for (const [pattern, label] of WORK_ALIASES) {
    if (pattern.test(normalized)) return label;
  }
  const words = normalized
    .split(" ")
    .filter((word) => !/^t\s*=/i.test(word))
    .filter(Boolean);
  return words.length ? words.slice(0, 3).join(" ") : null;
}

export type LabelMode = "none" | "code" | "full";

/** Full labels at close zoom, codes at medium zoom, nothing when zoomed out. */
export function labelModeForZoom(zoom: number): LabelMode {
  if (zoom >= 1.3) return "full";
  if (zoom >= 1.05) return "code";
  return "none";
}

export type VisibleLabel = {
  target: MapTarget;
  text: string;
  fontPx: number;
  status: string;
};

type LabelRect = { left: number; top: number; right: number; bottom: number };

function labelsOverlap(a: LabelRect, b: LabelRect, gap = 2): boolean {
  return !(
    a.right + gap < b.left ||
    b.right + gap < a.left ||
    a.bottom + gap < b.top ||
    b.bottom + gap < a.top
  );
}

/**
 * Greedy screen-space collision skip. Positions are screen px relative to the
 * image; pan is common to all labels so it cannot change overlaps.
 */
export function layoutMarkerLabels(
  targets: ReadonlyArray<MapTarget>,
  mode: LabelMode,
  zoom: number,
  imageBox: { width: number; height: number },
): VisibleLabel[] {
  if (
    mode === "none" ||
    !Number.isFinite(imageBox.width) ||
    !Number.isFinite(imageBox.height) ||
    imageBox.width <= 0 ||
    imageBox.height <= 0
  ) {
    return [];
  }
  const fontPx = mode === "full" ? 12 : 11;
  const placed: LabelRect[] = [];
  const visible: VisibleLabel[] = [];
  for (const target of targets) {
    const short = abbreviateWorkName(
      target.marker.current_work_name ??
        target.marker.current_work ??
        target.marker.current_stage_name,
    );
    const text =
      mode === "full" && short
        ? `${target.marker.code} · ${short}`
        : target.marker.code;
    const width = Math.max(24, text.length * fontPx * 0.58);
    const height = fontPx + 4;
    const centerX = target.x * imageBox.width * zoom;
    const top = target.y * imageBox.height * zoom + 8;
    const rect = {
      left: centerX - width / 2,
      top,
      right: centerX + width / 2,
      bottom: top + height,
    };
    if (placed.some((existing) => labelsOverlap(existing, rect))) continue;
    placed.push(rect);
    visible.push({
      target,
      text,
      fontPx,
      status:
        target.marker.current_work_status ??
        target.marker.construction_status,
    });
  }
  return visible;
}

export type ScreenTarget = {
  marker: DrawingMarker;
  points: Array<[number, number]>;
};

export type MarkerHit = {
  marker: DrawingMarker;
  distance: number;
};

export const PILE_HIT_PX = 22;
export const BEAM_HIT_PX = 14;
export const HIT_AMBIGUITY_PX = 4;

export function pointToSegmentDistance(
  point: [number, number],
  start: [number, number],
  end: [number, number],
): number {
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  if (dx === 0 && dy === 0) {
    return Math.hypot(point[0] - start[0], point[1] - start[1]);
  }
  const t = Math.max(
    0,
    Math.min(
      1,
      ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) /
        (dx * dx + dy * dy),
    ),
  );
  return Math.hypot(
    point[0] - (start[0] + t * dx),
    point[1] - (start[1] + t * dy),
  );
}

function distanceToMarker(
  point: [number, number],
  target: ScreenTarget,
): number {
  if (target.points.length <= 1) {
    const only = target.points[0];
    return only
      ? Math.hypot(point[0] - only[0], point[1] - only[1])
      : Number.POSITIVE_INFINITY;
  }
  if (target.marker.type === "pile") {
    return Math.min(
      ...target.points.map(([x, y]) =>
        Math.hypot(point[0] - x, point[1] - y),
      ),
    );
  }
  let best = Number.POSITIVE_INFINITY;
  for (let index = 1; index < target.points.length; index += 1) {
    best = Math.min(
      best,
      pointToSegmentDistance(
        point,
        target.points[index - 1],
        target.points[index],
      ),
    );
  }
  return best;
}

/**
 * Nearest drawable geometry in screen px. Returns every candidate within a few
 * pixels of the winner so the UI can ask instead of guessing.
 */
export function hitTestMarkers(
  targets: ReadonlyArray<ScreenTarget>,
  tap: [number, number],
  options: { pileTolerance?: number; beamTolerance?: number; ambiguity?: number } = {},
): MarkerHit[] {
  const pileTolerance = options.pileTolerance ?? PILE_HIT_PX;
  const beamTolerance = options.beamTolerance ?? BEAM_HIT_PX;
  const ambiguity = options.ambiguity ?? HIT_AMBIGUITY_PX;
  const candidates = targets
    .flatMap((target) => {
      const distance = distanceToMarker(tap, target);
      const tolerance =
        target.marker.type === "pile" ? pileTolerance : beamTolerance;
      return distance <= tolerance ? [{ marker: target.marker, distance }] : [];
    })
    .sort(
      (a, b) =>
        a.distance - b.distance ||
        Number(b.marker.type === "beam") - Number(a.marker.type === "beam"),
    );
  if (!candidates.length) return [];
  const best = candidates[0].distance;
  return candidates.filter((candidate) => candidate.distance <= best + ambiguity);
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
