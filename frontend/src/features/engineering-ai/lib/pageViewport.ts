export const MIN_PAGE_ZOOM = 1;
export const MAX_PAGE_ZOOM = 4;
export const PAGE_ZOOM_STEP = 0.25;

export function clampPageZoom(value: number): number {
  if (!Number.isFinite(value)) {
    return MIN_PAGE_ZOOM;
  }
  return Math.min(MAX_PAGE_ZOOM, Math.max(MIN_PAGE_ZOOM, Math.round(value * 100) / 100));
}

export function stepPageZoom(current: number, direction: 1 | -1): number {
  return clampPageZoom(current + direction * PAGE_ZOOM_STEP);
}
