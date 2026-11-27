/** Read-only pilot drawing map: project-scoped fetch, filters and viewport math. */

import { ApiError, apiFetch } from "./api";
import { getDrawingImageBlob } from "./drawingImageCache";
import type { SchematicPlan } from "./schematicMap";

export type DrawingMarker = {
  component_id: string;
  code: string;
  type: "pile" | "beam";
  zone?: string;
  segment?: number;
  design_group?: string | null;
  location_review?: boolean;
  current_work?: string | null;
  current_work_definition_id?: string | null;
  current_work_name?: string | null;
  current_work_status?: string | null;
  current_stage_name?: string | null;
  current_stage_definition_id?: string | null;
  last_event_date?: string | null;
  accepted?: boolean;
  points: Array<[number, number]>;
  origin: string;
  construction_status: string;
  position_id?: string | null;
  position_status?: string | null;
  position_note?: string | null;
};

export type DrawingSheet = {
  id: string;
  title: string;
  drawing: string;
  page: number;
  image_url: string;
  zone?: string | null;
  segment?: number | null;
  markers: DrawingMarker[];
  /** Present when the sheet is a generated schematic, not a scanned image. */
  schematic?: SchematicPlan;
};

export type DrawingMap = {
  sheets: DrawingSheet[];
  review_count: number;
  position_review_count?: number;
};

export type DrawingFilters = {
  query: string;
  type: string;
  status: string;
  origin: string;
};

export const EMPTY_DRAWING_FILTERS: DrawingFilters = {
  query: "",
  type: "",
  status: "",
  origin: "",
};

export type ComponentScopeDetail = {
  id: string;
  kind: string;
  revision: number;
  verification: string;
  approval_reference?: string | null;
  reviewed_at?: string | null;
};

export type ComponentStageDetail = {
  id: string;
  code: string;
  name: string;
  status: string;
  latest_event_at?: string | null;
  inferred_from_stage_id?: string | null;
  inference_conflict?: boolean;
};

export type ComponentWorkLinkDetail = {
  dm_row: number;
  work: string;
  raw_location?: string | null;
};

/** Only the detail fields this panel renders; the endpoint returns more. */
export type ComponentDetail = {
  id: string;
  type: string;
  raw_code: string;
  canonical_code: string;
  verification: string;
  record_origin: string;
  aliases: string[];
  source?: {
    sha256?: string | null;
    sheet?: string | null;
    row?: number | null;
  } | null;
  design_group?: {
    name?: string | null;
    drawing?: string | null;
    source?: string | null;
    source_page?: number | string | null;
  } | null;
  scopes?: ComponentScopeDetail[];
  stages?: ComponentStageDetail[];
  work_links?: ComponentWorkLinkDetail[];
};

const CONSTRUCTION_STATUS_LABELS: Record<string, string> = {
  NOT_STARTED: "Chưa bắt đầu",
  IN_PROGRESS: "Đang thi công",
  COMPLETED: "Hoàn thành",
  BLOCKED: "Tạm dừng",
};

const SCOPE_LABELS: Record<string, string> = {
  DESIGN_SCOPE: "Thiết kế",
  ADDITIONAL_SCOPE: "Phát sinh",
};

export function constructionStatusLabel(status: string): string {
  return CONSTRUCTION_STATUS_LABELS[status] ?? status;
}

export function componentTypeLabel(type: string): string {
  if (type === "pile") return "Cọc";
  if (type === "beam") return "Dầm";
  return type;
}

export function originLabel(origin: string): string {
  return SCOPE_LABELS[origin] ?? origin;
}

export function isAdditionalScope(marker: DrawingMarker): boolean {
  return marker.origin === "ADDITIONAL_SCOPE";
}

const STATUS_COLORS: Record<string, string> = {
  NOT_STARTED: "#64748b",
  IN_PROGRESS: "#b45309",
  COMPLETED: "#15803d",
  BLOCKED: "#b91c1c",
};

/** Existing construction status tokens, usable as SVG stroke colours. */
export function constructionStatusColor(status: string): string {
  return STATUS_COLORS[status] ?? STATUS_COLORS.NOT_STARTED;
}

export const ACCEPTANCE_OUTLINE_COLOR = "#405e9b";

function normalizedZone(value: string | null | undefined): string {
  return (value ?? "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .trim()
    .toLowerCase();
}

/** Prefer the sheet that actually contains the batch's primary zone. */
export function pickPrimarySheet(
  sheets: ReadonlyArray<DrawingSheet>,
  primaryZone: string | null | undefined,
): DrawingSheet | null {
  if (!sheets.length) return null;
  const zone = normalizedZone(primaryZone);
  if (!zone) return sheets[0];
  let best = sheets[0];
  let bestCount = -1;
  for (const sheet of sheets) {
    const count = sheet.markers.filter(
      (marker) => normalizedZone(marker.zone) === zone,
    ).length;
    if (count > bestCount) {
      best = sheet;
      bestCount = count;
    }
  }
  return bestCount > 0 ? best : sheets[0];
}

export function designGroupColor(group: string | null | undefined): string | null {
  const name = (group ?? "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
  if (/\bnhom\s*(?:i|1)\b/.test(name)) return "#0f766e";
  if (/\bnhom\s*(?:ii|2)\b/.test(name)) return "#b45309";
  if (/\bnhom\s*(?:iii|3)\b/.test(name)) return "#7e22ce";
  return null;
}

function clampUnit(value: number): number {
  return Math.min(1, Math.max(0, value));
}

/** Defensive: the server normalises coordinates but the overlay must not trust bad data. */
export function sanitizePoints(
  points: ReadonlyArray<readonly [number, number]> | null | undefined,
): Array<[number, number]> {
  if (!Array.isArray(points)) return [];
  return points.flatMap((point) => {
    if (!Array.isArray(point) || point.length !== 2) return [];
    const x = Number(point[0]);
    const y = Number(point[1]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return [];
    return [[clampUnit(x), clampUnit(y)] as [number, number]];
  });
}

function searchable(value: string): string {
  return value.toLowerCase();
}

/**
 * Marker-level filters plus one search box. Search matches either the sheet
 * (drawing/title/page) or a marker code. With no active filter the sheet list
 * is kept as-is, including sheets that have no mapped marker.
 */
export function filterDrawingSheets(
  sheets: ReadonlyArray<DrawingSheet>,
  filters: DrawingFilters,
): DrawingSheet[] {
  const query = filters.query.trim().toLowerCase();
  const active = Boolean(
    query || filters.type || filters.status || filters.origin,
  );
  return sheets.flatMap((sheet) => {
    const sheetText = searchable(
      [sheet.id, sheet.title, sheet.drawing, String(sheet.page)].join(" "),
    );
    const sheetMatches = Boolean(query) && sheetText.includes(query);
    const markers = sheet.markers.filter((marker) => {
      if (filters.type && marker.type !== filters.type) return false;
      if (filters.status && marker.construction_status !== filters.status) {
        return false;
      }
      if (filters.origin && marker.origin !== filters.origin) return false;
      if (!query) return true;
      return sheetMatches || searchable(marker.code).includes(query);
    });
    if (active && markers.length === 0) return [];
    return [{ ...sheet, markers }];
  });
}

export function countMarkers(sheets: ReadonlyArray<DrawingSheet>): number {
  return sheets.reduce((total, sheet) => total + sheet.markers.length, 0);
}

export type ImageBox = {
  left: number;
  top: number;
  width: number;
  height: number;
};

/**
 * Where an `object-fit: contain` image really lands inside its element.
 * Normalised marker points are drawn only inside this measured box.
 */
export function containBox(
  naturalWidth: number,
  naturalHeight: number,
  boxWidth: number,
  boxHeight: number,
): ImageBox | null {
  if (
    ![naturalWidth, naturalHeight, boxWidth, boxHeight].every(
      (value) => Number.isFinite(value) && value > 0,
    )
  ) {
    return null;
  }
  const scale = Math.min(boxWidth / naturalWidth, boxHeight / naturalHeight);
  const width = naturalWidth * scale;
  const height = naturalHeight * scale;
  return {
    left: (boxWidth - width) / 2,
    top: (boxHeight - height) / 2,
    width,
    height,
  };
}

export type Pan = { x: number; y: number };
export type View = { zoom: number; pan: Pan };
export type MarkerBounds = {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
};

export const MIN_ZOOM = 1;
export const MAX_ZOOM = 4;

export function clampZoom(value: number): number {
  if (!Number.isFinite(value)) return MIN_ZOOM;
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
}

/** Keep the zoomed image covering the viewport so it cannot be dragged away. */
export function clampPan(
  pan: Pan,
  zoom: number,
  viewportWidth: number,
  viewportHeight: number,
): Pan {
  const z = clampZoom(zoom);
  if (z === MIN_ZOOM) return { x: 0, y: 0 };
  const maxX = Math.max(0, ((z - 1) * viewportWidth) / 2);
  const maxY = Math.max(0, ((z - 1) * viewportHeight) / 2);
  const x = Number.isFinite(pan.x) ? pan.x : 0;
  const y = Number.isFinite(pan.y) ? pan.y : 0;
  return {
    x: Math.min(maxX, Math.max(-maxX, x)),
    y: Math.min(maxY, Math.max(-maxY, y)),
  };
}

export function pinchZoom(
  startZoom: number,
  startDistance: number,
  currentDistance: number,
): number {
  if (!Number.isFinite(startDistance) || startDistance <= 0) {
    return clampZoom(startZoom);
  }
  if (!Number.isFinite(currentDistance) || currentDistance <= 0) {
    return clampZoom(startZoom);
  }
  return clampZoom(startZoom * (currentDistance / startDistance));
}

/** Normalised bounding box of every drawable marker point on one sheet. */
export function markerBounds(
  markers: ReadonlyArray<DrawingMarker>,
): MarkerBounds | null {
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  for (const marker of markers) {
    for (const [x, y] of sanitizePoints(marker.points)) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }
  if (!Number.isFinite(minX) || !Number.isFinite(minY)) return null;
  return { minX, minY, maxX, maxY };
}

/**
 * Fit a normalised marker box inside the measured image box with padding.
 * Pan is expressed in the same centre-scaled coordinates as the CSS transform.
 */
export function fitViewToBounds(
  bounds: MarkerBounds | null,
  imageBox: ImageBox,
  viewportWidth: number,
  viewportHeight: number,
  padding = 0.08,
): View | null {
  if (
    !bounds ||
    !imageBox ||
    ![imageBox.width, imageBox.height, viewportWidth, viewportHeight].every(
      (value) => Number.isFinite(value) && value > 0,
    )
  ) {
    return null;
  }
  const pad = Math.min(0.45, Math.max(0, padding));
  const minSpan = 0.02;
  const centerX = (bounds.minX + bounds.maxX) / 2;
  const centerY = (bounds.minY + bounds.maxY) / 2;
  const width = Math.max(bounds.maxX - bounds.minX, minSpan) * imageBox.width;
  const height = Math.max(bounds.maxY - bounds.minY, minSpan) * imageBox.height;
  const zoom = clampZoom(
    Math.min(
      (viewportWidth * (1 - 2 * pad)) / width,
      (viewportHeight * (1 - 2 * pad)) / height,
    ),
  );
  const imageCenterX = imageBox.left + centerX * imageBox.width;
  const imageCenterY = imageBox.top + centerY * imageBox.height;
  return {
    zoom,
    pan: clampPan(
      {
        x: (viewportWidth / 2 - imageCenterX) * zoom,
        y: (viewportHeight / 2 - imageCenterY) * zoom,
      },
      zoom,
      viewportWidth,
      viewportHeight,
    ),
  };
}

export type ViewportFitState = {
  activeSheetKey: string;
  fittedSheetKey: string | null;
};

export type ViewportFitEvent =
  | { type: "open"; sheetKey: string; imageReady: boolean }
  | { type: "reset"; imageReady: boolean }
  | { type: "gesture" }
  | { type: "metrics" }
  | { type: "data" }
  | { type: "selection" };

/**
 * The viewport fits once per sheet. Metrics, data refreshes, label density,
 * selection and cache swaps never move it; only a sheet open or an explicit
 * "fit" request does. A gesture consumes the pending first fit immediately.
 */
export function viewportFitStep(
  state: ViewportFitState,
  event: ViewportFitEvent,
): { state: ViewportFitState; fit: boolean } {
  if (event.type === "open") {
    const next = { ...state, activeSheetKey: event.sheetKey };
    const fit =
      event.imageReady && next.fittedSheetKey !== event.sheetKey;
    if (fit) next.fittedSheetKey = event.sheetKey;
    return { state: next, fit };
  }
  if (event.type === "reset") {
    const fit = event.imageReady && Boolean(state.activeSheetKey);
    return {
      state: fit ? { ...state, fittedSheetKey: state.activeSheetKey } : state,
      fit,
    };
  }
  if (event.type === "gesture") {
    return {
      state: state.activeSheetKey
        ? { ...state, fittedSheetKey: state.activeSheetKey }
        : state,
      fit: false,
    };
  }
  return { state, fit: false };
}

export type ViewportRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

/**
 * Inverse of the CSS transform used on the sheet: screen point -> normalised
 * sheet point. Returns null outside the drawn image so taps on the letterbox
 * do not create off-sheet positions.
 */
export function clientToSheetPoint(
  client: { x: number; y: number },
  rect: ViewportRect,
  imageBox: ImageBox,
  view: View,
): [number, number] | null {
  if (
    ![rect.width, rect.height, imageBox.width, imageBox.height].every(
      (value) => Number.isFinite(value) && value > 0,
    )
  ) {
    return null;
  }
  const zoom = clampZoom(view.zoom);
  const x =
    (client.x - rect.left - rect.width / 2 - view.pan.x) / zoom +
    rect.width / 2;
  const y =
    (client.y - rect.top - rect.height / 2 - view.pan.y) / zoom +
    rect.height / 2;
  const u = (x - imageBox.left) / imageBox.width;
  const v = (y - imageBox.top) / imageBox.height;
  if (!Number.isFinite(u) || !Number.isFinite(v)) return null;
  if (u < 0 || u > 1 || v < 0 || v > 1) return null;
  return [u, v];
}

/** Forward transform: normalised sheet point -> client coordinates. */
export function sheetToClient(
  point: [number, number],
  rect: ViewportRect,
  imageBox: ImageBox,
  view: View,
): [number, number] {
  const zoom = clampZoom(view.zoom);
  const x =
    rect.left +
    rect.width / 2 +
    (imageBox.left + point[0] * imageBox.width - rect.width / 2) * zoom +
    view.pan.x;
  const y =
    rect.top +
    rect.height / 2 +
    (imageBox.top + point[1] * imageBox.height - rect.height / 2) * zoom +
    view.pan.y;
  return [x, y];
}

/** Zoom around a client point while keeping that sheet point under the finger. */
export function zoomAroundPoint(
  view: View,
  clientPoint: { x: number; y: number },
  targetZoom: number,
  rect: ViewportRect,
): View {
  const startZoom = clampZoom(view.zoom);
  const zoom = clampZoom(targetZoom);
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  const imageX =
    centerX + (clientPoint.x - centerX - view.pan.x) / startZoom;
  const imageY =
    centerY + (clientPoint.y - centerY - view.pan.y) / startZoom;
  return {
    zoom,
    pan: clampPan(
      {
        x: clientPoint.x - centerX - (imageX - centerX) * zoom,
        y: clientPoint.y - centerY - (imageY - centerY) * zoom,
      },
      zoom,
      rect.width,
      rect.height,
    ),
  };
}

/**
 * Pinch around the midpoint between both fingers. The sheet point under the
 * initial midpoint follows the current midpoint while the distance controls
 * zoom, so zoom and two-finger pan happen in one transform.
 */
export function pinchView(
  startView: View,
  startMidpoint: { x: number; y: number },
  currentMidpoint: { x: number; y: number },
  targetZoom: number,
  rect: ViewportRect,
): View {
  const startZoom = clampZoom(startView.zoom);
  const zoom = clampZoom(targetZoom);
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  const imageX =
    centerX + (startMidpoint.x - centerX - startView.pan.x) / startZoom;
  const imageY =
    centerY + (startMidpoint.y - centerY - startView.pan.y) / startZoom;
  return {
    zoom,
    pan: clampPan(
      {
        x: currentMidpoint.x - centerX - (imageX - centerX) * zoom,
        y: currentMidpoint.y - centerY - (imageY - centerY) * zoom,
      },
      zoom,
      rect.width,
      rect.height,
    ),
  };
}

/** CSS transform for one wrapper; keep the marker/label layer in the same node. */
export function viewTransform(view: View): string {
  return `translate3d(${view.pan.x}px, ${view.pan.y}px, 0) scale(${view.zoom})`;
}

/** Accept both `/projects/...` and `/api/v1/projects/...` from the server. */
export function apiRelativePath(url: string): string {
  const trimmed = url.trim();
  const prefix = "/api/v1";
  return trimmed.startsWith(`${prefix}/`) ? trimmed.slice(prefix.length) : trimmed;
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

export async function fetchDrawingMap(
  projectId: string,
  batchId?: string | null,
  signal?: AbortSignal,
  filters?: { zone?: string | null; segment?: number | null },
): Promise<DrawingMap> {
  const params = new URLSearchParams();
  if (batchId) params.set("batch_id", batchId);
  if (filters?.zone) params.set("zone", filters.zone);
  if (filters?.segment != null) params.set("segment", String(filters.segment));
  const query = params.toString();
  const res = await apiFetch(
    `/projects/${projectId}/drawing-map${query ? `?${query}` : ""}`,
    { signal },
  );
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

export type MapPositionInput = {
  sheet_id: string;
  points: Array<[number, number]>;
  note?: string | null;
};

export type MapPosition = {
  id: string;
  component_id: string;
  sheet_id: string;
  points: Array<[number, number]>;
  status: string;
  source: string;
  note: string | null;
  reviewed_at?: string | null;
};

export async function saveDrawingMapPosition(
  projectId: string,
  componentId: string,
  payload: MapPositionInput,
): Promise<MapPosition> {
  const res = await apiFetch(
    `/projects/${projectId}/components/${componentId}/map-position`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

export async function reviewDrawingMapPosition(
  projectId: string,
  componentId: string,
  sheetId: string,
): Promise<MapPosition> {
  const res = await apiFetch(
    `/projects/${projectId}/components/${componentId}/map-position/review?sheet_id=${encodeURIComponent(sheetId)}`,
    { method: "POST" },
  );
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

/** Private sheet bytes, served from the versioned private cache when possible. */
export async function fetchDrawingSheetImageUrl(
  imageUrl: string,
  signal?: AbortSignal,
  skipCache = false,
): Promise<string> {
  return URL.createObjectURL(
    await getDrawingImageBlob(imageUrl, signal, skipCache),
  );
}

export async function fetchComponentDetail(
  projectId: string,
  componentId: string,
  signal?: AbortSignal,
): Promise<ComponentDetail> {
  const res = await apiFetch(
    `/projects/${projectId}/components/${componentId}`,
    { signal },
  );
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}
