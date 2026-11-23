import { ArrowRightIcon } from "./AppIcons";
import {
  componentUnit,
  formatLatestDayLine,
  formatSegmentLabel,
  formatShortDate,
  uniqueCodes,
  type LatestDay,
} from "./overviewFormat";

export default function LatestDayCard({
  day,
  failed,
  onOpenSite,
}: {
  day: LatestDay | null;
  failed: boolean;
  onOpenSite?: () => void;
}) {
  const codes = day ? uniqueCodes(day.works) : [];

  return (
    <section className="app-card app-card-pad" aria-labelledby="latest-day-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="latest-day-title" className="text-base font-semibold text-slate-950">
            Báo cáo ngày gần nhất
          </h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Ngày gần nhất có tiến độ thi công hoặc báo cáo ngày đã ghi.
          </p>
        </div>
        {onOpenSite && (
          <button type="button" className="app-button app-button-secondary min-h-10 px-3" onClick={onOpenSite}>
            Mở Hiện trường <ArrowRightIcon className="h-4 w-4" />
          </button>
        )}
      </div>

      {failed ? (
        <p role="alert" className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          Chưa tải được báo cáo ngày gần nhất.
        </p>
      ) : !day ? (
        <p role="status" className="mt-3 text-sm text-slate-600">Đang tải báo cáo ngày gần nhất…</p>
      ) : !day.date ? (
        <p className="mt-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
          Chưa có báo cáo ngày hoặc tiến độ thi công.
        </p>
      ) : (
        <>
          <p className="mt-3 text-sm font-semibold leading-6 text-slate-900">{formatLatestDayLine(day)}</p>
          <ul className="mt-3 flex flex-wrap gap-2 text-xs" aria-label="Thông tin ngày gần nhất">
            <li className="app-badge bg-white text-slate-700">
              Nhân lực: <span className="ml-1 font-semibold tabular-nums">{day.manpower_total ?? "—"}</span>
            </li>
            <li className="app-badge bg-white text-slate-700">
              Ảnh: <span className="ml-1 font-semibold tabular-nums">{day.photo_count}</span>
            </li>
            <li className="app-badge bg-white text-slate-700">
              Báo cáo ngày: <span className="ml-1 font-semibold">{day.daily_report_exists ? "Đã ghi" : "Chưa có"}</span>
            </li>
            {day.acceptance_today.length > 0 && (
              <li className="app-badge bg-white text-slate-700">
                Nghiệm thu: <span className="ml-1 font-semibold tabular-nums">{day.acceptance_today.length}</span>
              </li>
            )}
          </ul>

          {day.works.length > 0 && (
            <details className="mt-3 rounded-xl border border-slate-200 bg-white">
              <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 text-sm font-medium text-slate-800 [&::-webkit-details-marker]:hidden">
                Danh sách mã cấu kiện
                <span className="text-xs font-normal text-slate-500">{codes.length} mã</span>
              </summary>
              <div className="space-y-3 border-t border-slate-100 px-4 py-3">
                {day.works.map((work) => (
                  <div key={`${work.stage_name}|${work.zone}|${work.segment}|${work.status}`}>
                    <p className="text-xs font-medium text-slate-700">
                      {work.stage_name} · {formatSegmentLabel(work.zone, work.segment)} · {work.count} {componentUnit(work.component_type)}
                    </p>
                    <p className="mt-1 break-words text-xs leading-5 text-slate-600">{work.codes.join(", ")}</p>
                  </div>
                ))}
              </div>
            </details>
          )}

          <p className="mt-3 text-xs text-slate-500">
            Ngày ghi nhận {formatShortDate(day.date)} · Nghiệm thu chỉ lấy từ BBNT đã xác nhận.
          </p>
        </>
      )}
    </section>
  );
}
