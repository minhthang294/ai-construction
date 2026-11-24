/** Pure helpers and shared class tokens for the component catalog import panel. */

import { ApiError } from "./api";
import type {
  ComponentSegment,
  ComponentType,
  ComponentScope,
} from "./componentImport";

export const PAGE_SIZE = 100;

export const COMPONENT_VIEWS = [
  { id: "daily", label: "Ghi theo ngày" },
  { id: "progress", label: "Theo cấu kiện" },
  { id: "catalog", label: "Danh mục" },
  { id: "journal", label: "Nhật ký" },
  { id: "map", label: "Mặt bằng" },
] as const;
export type ComponentView = (typeof COMPONENT_VIEWS)[number]["id"];

export type ComponentImportBusy = "preview" | "commit" | null;

export const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-700 focus-visible:ring-offset-2";
export const FIELD_CLASS = `min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-base text-slate-900 placeholder:text-slate-400 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-slate-500 ${FOCUS_RING}`;
export const PRIMARY_BUTTON = `min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-semibold text-white active:bg-slate-900 disabled:cursor-not-allowed disabled:bg-gray-300 ${FOCUS_RING}`;
export const SECONDARY_BUTTON = `min-h-11 rounded-lg border border-gray-300 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-gray-100 ${FOCUS_RING}`;
export const DETAILS_SUMMARY = `flex min-h-11 cursor-pointer flex-wrap items-center justify-between gap-2 px-3 py-2 text-left ${FOCUS_RING}`;

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Không xác định được lỗi.";
}

export function segmentLabel(segment: ComponentSegment): string {
  return `${segment.zone} · PĐ ${segment.number}`;
}

export function componentTypeLabel(type: ComponentType): string {
  return type === "pile" ? "Cọc" : "Dầm";
}

export function componentScopeLabel(scope: ComponentScope): string {
  return scope === "ADDITIONAL_SCOPE" ? "Phát sinh sửa chữa" : "Theo thiết kế";
}

/** Catalog list badge; the server owns the verification value. */
export function catalogVerificationLabel(value: string): string {
  return value === "VERIFIED" ? "Đã duyệt danh mục" : "Chờ duyệt";
}

export function catalogEmptyMessage(search: string): string {
  return search.trim()
    ? "Không tìm thấy cấu kiện khớp mã hoặc alias."
    : "Chưa có cấu kiện trong công trình.";
}

/** Roving tabindex target for Home/End/Arrow keys; -1 means not a nav key. */
export function nextViewIndex(current: number, key: string): number {
  const last = COMPONENT_VIEWS.length - 1;
  if (key === "Home") return 0;
  if (key === "End") return last;
  if (key === "ArrowRight") return (current + 1) % COMPONENT_VIEWS.length;
  if (key === "ArrowLeft") return (current + last) % COMPONENT_VIEWS.length;
  return -1;
}

export function pageRemaining(total: number, visible: number): number {
  return Math.min(PAGE_SIZE, total - visible);
}
