/** Component detail presentation: compact bottom sheet and full panel. */

import {
  componentTypeLabel,
  constructionStatusLabel,
  originLabel,
  type ComponentDetail,
  type DrawingMarker,
} from "../lib/drawingMap";
import {
  BUTTON,
  FOCUS_RING,
  PRIMARY_BUTTON,
  formatShortMapDate,
  recordOriginLabel,
  shortSha,
  statusChipClass,
  verificationLabel,
  type Placement,
} from "../lib/drawingMapPanel";
import type { DetailState } from "./useDrawingMapDetail";

function StatusChip({ status }: { status: string }) {
  return (
    <span className={statusChipClass(status)}>
      {constructionStatusLabel(status)}
    </span>
  );
}

type CompactProps = {
  detailMarker: DrawingMarker;
  closeDetail: () => void;
  onOpenComponent?: (componentId: string) => void;
  onRequestProgress?: (
    componentId: string,
    stageDefinitionId?: string | null,
  ) => void;
};

export function DrawingMapCompactDetail({
  detailMarker,
  closeDetail,
  onOpenComponent,
  onRequestProgress,
}: CompactProps) {
  return (
    <div className="absolute inset-x-0 bottom-0 z-30 max-h-[75%] overflow-y-auto rounded-t-2xl border-t border-slate-300 bg-white p-3 shadow-[0_-8px_24px_rgba(15,23,42,0.18)]">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500">Chi tiết cấu kiện</p>
          <h4 className="break-words font-mono text-base font-semibold text-slate-900">
            {detailMarker.code}
          </h4>
        </div>
        <button
          type="button"
          className={`${BUTTON} shrink-0 ${FOCUS_RING}`}
          onClick={closeDetail}
        >
          Đóng
        </button>
      </div>
      <dl className="mt-2 grid grid-cols-[7rem_minmax(0,1fr)] gap-x-2 gap-y-1 text-sm">
        <dt className="text-slate-600">Công đoạn</dt>
        <dd className="break-words text-slate-900">
          {detailMarker.current_work_name ||
            detailMarker.current_stage_name ||
            detailMarker.current_work ||
            "Chưa có công đoạn"}
        </dd>
        <dt className="text-slate-600">Cập nhật cuối</dt>
        <dd className="text-slate-900">
          {detailMarker.last_event_date
            ? formatShortMapDate(detailMarker.last_event_date)
            : "Chưa có sự kiện"}
        </dd>
        <dt className="text-slate-600">Nghiệm thu</dt>
        <dd className="text-slate-900">
          {detailMarker.accepted ? "Đã nghiệm thu" : "Chưa nghiệm thu"}
        </dd>
        <dt className="text-slate-600">Thi công</dt>
        <dd className="text-slate-900">
          {constructionStatusLabel(detailMarker.construction_status)}
        </dd>
      </dl>
      <div className="mt-3 grid gap-2 min-[375px]:grid-cols-2">
        <button
          type="button"
          className={`${BUTTON} w-full ${FOCUS_RING}`}
          disabled={!onOpenComponent}
          onClick={() => onOpenComponent?.(detailMarker.component_id)}
        >
          Mở chi tiết
        </button>
        <button
          type="button"
          className={`${PRIMARY_BUTTON} w-full ${FOCUS_RING}`}
          disabled={!onRequestProgress}
          onClick={() =>
            onRequestProgress?.(
              detailMarker.component_id,
              detailMarker.current_stage_definition_id ??
                detailMarker.current_work_definition_id,
            )
          }
        >
          Ghi tiến độ
        </button>
      </div>
    </div>
  );
}

type Props = {
  detailMarker: DrawingMarker;
  detail: ComponentDetail | null;
  detailState: DetailState;
  detailError: string | null;
  openDetail: (marker: DrawingMarker) => void;
  closeDetail: () => void;
  startOverride: (marker: DrawingMarker) => void;
  reviewPosition: (marker: DrawingMarker) => void;
  reviewBusyId: string | null;
  placement: Placement | null;
  onRequestProgress?: (
    componentId: string,
    stageDefinitionId?: string | null,
  ) => void;
  detailHeadingId: string;
  detailHeadingRef: React.RefObject<HTMLHeadingElement | null>;
};

export default function DrawingMapDetailPanel({
  detailMarker,
  detail,
  detailState,
  detailError,
  openDetail,
  closeDetail,
  startOverride,
  reviewPosition,
  reviewBusyId,
  placement,
  onRequestProgress,
  detailHeadingId,
  detailHeadingRef,
}: Props) {
  return (
    <section
      aria-labelledby={detailHeadingId}
      className="rounded-xl border border-slate-300 bg-white p-3 shadow-sm"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500">
            Chi tiết cấu kiện
          </p>
          <h4
            id={detailHeadingId}
            ref={detailHeadingRef}
            tabIndex={-1}
            className="break-words font-mono text-base font-semibold text-slate-900 focus:outline-none"
          >
            {detail?.canonical_code ?? detailMarker.code}
          </h4>
          <p className="mt-1 text-xs text-slate-600">
            {componentTypeLabel(detailMarker.type)} ·{" "}
            {constructionStatusLabel(
              detailMarker.construction_status,
            )}{" "}
            · {originLabel(detailMarker.origin)}
          </p>
        </div>
        <button
          type="button"
          aria-label="Đóng chi tiết cấu kiện"
          className={`${BUTTON} shrink-0 ${FOCUS_RING}`}
          onClick={closeDetail}
        >
          Đóng
        </button>
      </div>

      {onRequestProgress ? (
        <button
          type="button"
          className={`${PRIMARY_BUTTON} mt-3 w-full ${FOCUS_RING}`}
          onClick={() => onRequestProgress(detailMarker.component_id, detailMarker.current_work_definition_id)}
        >
          Ghi tiến độ theo ngày
        </button>
      ) : null}

      <div className="mt-3 grid gap-2 min-[375px]:grid-cols-2">
        <button
          type="button"
          className={`${BUTTON} w-full ${FOCUS_RING}`}
          disabled={Boolean(placement)}
          onClick={() => startOverride(detailMarker)}
        >
          Đặt lại vị trí
        </button>
        {detailMarker.position_id &&
        detailMarker.position_status === "DRAFT" ? (
          <button
            type="button"
            className={`${PRIMARY_BUTTON} w-full ${FOCUS_RING}`}
            disabled={reviewBusyId === detailMarker.component_id}
            onClick={() => void reviewPosition(detailMarker)}
          >
            {reviewBusyId === detailMarker.component_id
              ? "Đang duyệt…"
              : "Duyệt vị trí"}
          </button>
        ) : null}
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Đặt lại vị trí sẽ ghi đè vị trí bản vẽ và lưu vết kiểm
        toán. Chỉ quản lý dự án duyệt được vị trí.
      </p>

      {detailState === "loading" ? (
        <p className="mt-3 text-sm text-slate-600">
          Đang tải chi tiết cấu kiện…
        </p>
      ) : null}

      {detailState === "error" ? (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-900">
          <p role="alert">
            Không tải được chi tiết cấu kiện: {detailError}
          </p>
          <button
            type="button"
            className={`${BUTTON} mt-2 ${FOCUS_RING}`}
            onClick={() => void openDetail(detailMarker)}
          >
            Thử lại
          </button>
        </div>
      ) : null}

      {detailState === "ready" && detail ? (
        <div className="mt-3 space-y-3">
          <dl className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-x-2 gap-y-1 text-sm">
            <dt className="text-slate-600">Mã gốc</dt>
            <dd className="break-words font-mono text-slate-900">
              {detail.raw_code || "—"}
            </dd>
            <dt className="text-slate-600">Trạng thái duyệt</dt>
            <dd className="break-words text-slate-900">
              {verificationLabel(detail.verification)}
            </dd>
            <dt className="text-slate-600">Nguồn bản ghi</dt>
            <dd className="break-words text-slate-900">
              {recordOriginLabel(detail.record_origin)}
            </dd>
            <dt className="text-slate-600">Vị trí bản vẽ</dt>
            <dd className="break-words text-slate-900">
              {detailMarker.position_status === "DRAFT"
                ? "Nháp, chờ duyệt"
                : detailMarker.position_status === "REVIEWED"
                  ? "Đã duyệt"
                  : "Theo bản vẽ"}
            </dd>
            <dt className="text-slate-600">Bí danh</dt>
            <dd className="break-words text-slate-900">
              {detail.aliases?.length
                ? detail.aliases.join(", ")
                : "—"}
            </dd>
          </dl>

          {detail.design_group ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
              <h5 className="text-sm font-semibold text-slate-900">
                Nhóm thiết kế
              </h5>
              <p className="mt-1 break-words text-sm text-slate-800">
                {detail.design_group.name ?? "—"}
              </p>
              <p className="text-xs text-slate-600">
                {[
                  detail.design_group.drawing
                    ? `Bản vẽ ${detail.design_group.drawing}`
                    : null,
                  detail.design_group.source_page
                    ? `Trang ${detail.design_group.source_page}`
                    : null,
                  detail.design_group.source,
                ]
                  .filter(Boolean)
                  .join(" · ") || "—"}
              </p>
            </div>
          ) : null}

          {detail.scopes?.length ? (
            <div>
              <h5 className="text-sm font-semibold text-slate-900">
                Phạm vi sửa chữa
              </h5>
              <ul className="mt-1 space-y-1">
                {detail.scopes.map((scope) => (
                  <li
                    key={scope.id}
                    className="flex min-w-0 flex-wrap items-center gap-1 rounded-lg border border-slate-200 p-2 text-xs text-slate-700"
                  >
                    <span className="font-medium text-slate-900">
                      {originLabel(scope.kind)} · lần {scope.revision}
                    </span>
                    <span>{verificationLabel(scope.verification)}</span>
                    {scope.approval_reference ? (
                      <span className="break-words">
                        · Căn cứ: {scope.approval_reference}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {detail.stages?.length ? (
            <div>
              <h5 className="text-sm font-semibold text-slate-900">
                Bước thi công
              </h5>
              <ul className="mt-1 space-y-1">
                {detail.stages.map((stage) => (
                  <li
                    key={stage.id}
                    className="flex min-w-0 flex-wrap items-center justify-between gap-1 rounded-lg border border-slate-200 p-2 text-xs"
                  >
                    <span className="min-w-0 break-words text-slate-800">
                      {stage.name || stage.code}
                    </span>
                    <StatusChip status={stage.status} />
                    {stage.inference_conflict ? (
                      <span className="text-amber-800">Cần đối chiếu với bước sau</span>
                    ) : stage.inferred_from_stage_id ? (
                      <span className="text-slate-600">Suy ra từ bước sau</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {detail.work_links?.length ? (
            <div>
              <h5 className="text-sm font-semibold text-slate-900">
                Dòng danh mục công việc
              </h5>
              <ul className="mt-1 space-y-1">
                {detail.work_links.map((link) => (
                  <li
                    key={`${link.dm_row}-${link.work}`}
                    className="break-words rounded-lg border border-slate-200 p-2 text-xs text-slate-700"
                  >
                    <span className="font-medium text-slate-900">
                      DM dòng {link.dm_row}
                    </span>{" "}
                    · {link.work || "—"}
                    {link.raw_location
                      ? ` · ${link.raw_location}`
                      : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <p className="break-words text-xs text-slate-500">
            Nguồn: {shortSha(detail.source?.sha256)}
            {detail.source?.sheet
              ? ` · ${detail.source.sheet}`
              : ""}
            {detail.source?.row
              ? ` · dòng ${detail.source.row}`
              : ""}
          </p>
        </div>
      ) : null}
    </section>
  );
}
