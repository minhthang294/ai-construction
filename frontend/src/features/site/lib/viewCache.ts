// Pure cache selection/fallback logic for the latest viewed daily report.
// IndexedDB persistence lives in offlineDb.ts; this module stays browser-free.

export type ViewCacheRecord<
  TReport = unknown,
  TPhoto = unknown,
  TWorkItem = unknown,
> = {
  key: string;
  projectId: string;
  date: string;
  report: TReport;
  /** Photo metadata only; original bytes are never cached here. */
  photos: TPhoto[];
  workItems: TWorkItem[];
  cachedAt: number;
};

export type ViewSource = "server" | "cache" | "empty";

export function viewCacheKey(projectId: string, date: string): string {
  return `view:${projectId}:${date}`;
}

export function makeViewCacheRecord<
  TReport,
  TPhoto,
  TWorkItem,
>(input: {
  projectId: string;
  date: string;
  report: TReport;
  photos: TPhoto[];
  workItems: TWorkItem[];
  cachedAt?: number;
}): ViewCacheRecord<TReport, TPhoto, TWorkItem> {
  return {
    key: viewCacheKey(input.projectId, input.date),
    projectId: input.projectId,
    date: input.date,
    report: input.report,
    // Defensive copies keep callers from mutating the cached arrays later.
    photos: [...input.photos],
    workItems: [...input.workItems],
    cachedAt: input.cachedAt ?? Date.now(),
  };
}

/** Pick the newest snapshot with the exact project+date; ignore all others. */
export function selectCachedView<T extends ViewCacheRecord>(
  records: T[],
  projectId: string,
  date: string,
): T | undefined {
  return records
    .filter((record) => record.projectId === projectId && record.date === date)
    .sort((left, right) => right.cachedAt - left.cachedAt)[0];
}

/** Server wins when available; otherwise use a same-scope cache or nothing. */
export function decideViewSource(
  serverFailed: boolean,
  cached: ViewCacheRecord | undefined | null,
): ViewSource {
  if (!serverFailed) return "server";
  return cached ? "cache" : "empty";
}

/**
 * Work items, organizations and manpower contacts are project catalogs, not
 * report data. They are safe to fetch whenever the server is reachable, even
 * when the selected day has no daily report yet (GET returns 404 -> null).
 */
export function shouldLoadCatalogs(serverFailed: boolean): boolean {
  return !serverFailed;
}

const DATE_TIME = new Intl.DateTimeFormat("vi-VN", {
  timeZone: "Asia/Ho_Chi_Minh",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function formatCachedAt(cachedAt: number): string {
  const value = new Date(cachedAt);
  if (Number.isNaN(value.getTime())) return "không xác định";
  return DATE_TIME.format(value);
}

export function offlineDataLabel(cachedAt: number): string {
  return `Dữ liệu lưu trên thiết bị, cập nhật lúc ${formatCachedAt(cachedAt)}`;
}
