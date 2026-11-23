export type OverviewWork = {
  stage_name: string;
  zone: string;
  segment: number;
  component_type: string;
  status: string;
  count: number;
  codes: string[];
};

export type AcceptanceToday = {
  id: string;
  number?: string | null;
  request_number?: string | null;
  result?: string | null;
  record_date?: string | null;
  confirmed_at?: string | null;
  component_codes?: string[];
};

export type LatestDay = {
  date: string | null;
  works: OverviewWork[];
  manpower_total: number | null;
  photo_count: number;
  daily_report_exists: boolean;
  acceptance_today: AcceptanceToday[];
};

export type SegmentProgress = {
  zone: string;
  segment: number;
  segment_id: string;
  component_count: number;
  verified_components: number;
  construction: {
    not_started: number;
    in_progress: number;
    completed: number;
    blocked: number;
    completion_ratio: number;
  };
  acceptance: { confirmed: number; completion_ratio: number };
};

const percentage = new Intl.NumberFormat("vi-VN", {
  style: "percent",
  maximumFractionDigits: 1,
});

export function formatShortDate(value: string | null): string {
  if (!value) return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[3]}/${match[2]}` : value;
}

export function formatOverviewPercent(ratio: number): string {
  return percentage.format(Number.isFinite(ratio) ? ratio : 0);
}

export function componentUnit(type: string): string {
  if (type === "pile") return "cọc";
  if (type === "beam") return "dầm";
  return "cấu kiện";
}

export function workStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    COMPLETED: "hoàn thành",
    IN_PROGRESS: "đang thi công",
    BLOCKED: "tạm dừng",
    NOT_STARTED: "chưa bắt đầu",
  };
  return labels[status] ?? status;
}

export function formatSegmentLabel(zone: string, segment: number): string {
  return `PD${segment} · ${zone}`;
}

export function uniqueCodes(works: OverviewWork[]): string[] {
  return [...new Set(works.flatMap((work) => work.codes))].sort();
}

export function formatLatestDayLine(day: LatestDay): string {
  if (!day.date) return "Chưa có báo cáo ngày hoặc tiến độ thi công.";
  const date = formatShortDate(day.date);
  if (day.works.length === 0) return `${date} · Chưa có công tác ghi nhận`;
  const primary = day.works.reduce((best, work) =>
    work.count > best.count ? work : best,
  );
  const line = `${date} · ${primary.stage_name} · PD${primary.segment} ${primary.zone} · ${primary.count} ${componentUnit(primary.component_type)} ${workStatusLabel(primary.status)}`;
  const others = day.works.length - 1;
  return others > 0 ? `${line} · +${others} nhóm công tác khác` : line;
}
