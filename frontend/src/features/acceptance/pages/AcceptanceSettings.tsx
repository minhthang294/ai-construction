import AcceptanceHistoryPanel from "../components/AcceptanceHistoryPanel";
import NumberingPanel from "../components/NumberingPanel";
import ParticipantLibrary from "../components/ParticipantLibrary";
import type { ParticipantProfile } from "../types";

type Props = {
  projectId: string;
  onProfilesChanged: (profiles: ParticipantProfile[]) => void;
  onRefresh: () => void;
  onOpenRequest: (requestId: string) => void;
  onOpenRecord: (recordId: string) => void;
};

export default function AcceptanceSettings({
  projectId,
  onProfilesChanged,
  onRefresh,
  onOpenRequest,
  onOpenRecord,
}: Props) {
  return (
    <>
      <details className="rounded-xl bg-white p-4 shadow-sm">
        <summary className="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-semibold text-slate-800">
          Cài đặt nghiệm thu
          <span className="ml-auto text-sm font-normal text-slate-500">
            Danh bạ &amp; cấu hình số
          </span>
        </summary>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <ParticipantLibrary projectId={projectId} onChanged={onProfilesChanged} />
          <NumberingPanel projectId={projectId} onSaved={onRefresh} />
        </div>
      </details>

      <AcceptanceHistoryPanel
        projectId={projectId}
        onOpenRequest={onOpenRequest}
        onOpenRecord={onOpenRecord}
      />
    </>
  );
}
