/** Read-only pilot drawing map: project-scoped fetch, filters and viewport math. */

import { ApiError, apiFetch } from "./api";

export type DrawingMarker = {
  component_id: string;
  code: string;
  type: "pile" | "beam";
  design_group?: string | null;
  location_review?: boolean;
  current_work?: string | null;
  current_work_definition_id?: string | null;
  points: Array<[number, number]>;
  origin: string;
  construction_status: string;
};

export type DrawingSheet = {
  id: string;
  title: string;
  drawing: string;
  page: number;
  image_url: string;
  markers: DrawingMarker[];
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
  signal?: AbortSignal,
): Promise<DrawingMap> {
  const res = await apiFetch(`/projects/${projectId}/drawing-map`, { signal });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

/** Private sheet bytes fetched with the bearer token; caller revokes the URL. */
export async function fetchDrawingSheetImageUrl(
  imageUrl: string,
  signal?: AbortSignal,
): Promise<string> {
  const res = await apiFetch(apiRelativePath(imageUrl), { signal });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return URL.createObjectURL(await res.blob());
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
