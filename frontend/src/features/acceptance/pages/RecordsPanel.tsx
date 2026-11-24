import RecordDraftEditor from "./RecordDraftEditor";
import RecordSelector from "./RecordSelector";
import type { RecordDraft } from "./acceptancePageModel";
import type {
  AcceptanceRecord,
  AcceptanceRequest,
  LinkedDailyReport,
} from "../types";

type Props = {
  projectId: string;
  requests: AcceptanceRequest[];
  draft: RecordDraft | null;
  message: string | null;
  error: string | null;
  busy: boolean;
  reportLinks: Record<string, LinkedDailyReport | null>;
  recordFor: (requestId: string) => AcceptanceRecord | undefined;
  onStartRecord: (request: AcceptanceRequest) => void;
  onUpdateDraft: (updater: (current: RecordDraft) => RecordDraft) => void;
  onSave: () => void;
  onClose: () => void;
  onConfirm: () => void;
  onPreview: () => void;
  onRevision: () => void;
  onExport: (kind: "pyc" | "bbnt", format: "xlsx" | "pdf") => void;
};

export default function RecordsPanel({
  projectId,
  requests,
  draft,
  message,
  error,
  busy,
  reportLinks,
  recordFor,
  onStartRecord,
  onUpdateDraft,
  onSave,
  onClose,
  onConfirm,
  onPreview,
  onRevision,
  onExport,
}: Props) {
  return (
    <div className="space-y-4">
      {message && !draft && (
        <p role="status" className="rounded bg-emerald-50 p-3 text-sm text-emerald-900">
          {message}
        </p>
      )}
      {!draft && (
        <RecordSelector
          requests={requests}
          recordFor={recordFor}
          onStartRecord={onStartRecord}
        />
      )}

      {draft && (
        <RecordDraftEditor
          projectId={projectId}
          draft={draft}
          message={message}
          error={error}
          busy={busy}
          reportLinks={reportLinks}
          onUpdate={onUpdateDraft}
          onSave={onSave}
          onClose={onClose}
          onConfirm={onConfirm}
          onPreview={onPreview}
          onRevision={onRevision}
          onExport={onExport}
        />
      )}
    </div>
  );
}
