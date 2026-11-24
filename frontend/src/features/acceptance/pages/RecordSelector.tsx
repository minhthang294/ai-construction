import { recordPickerActionLabel, recordPickerLabel } from "./acceptancePageModel";
import type { AcceptanceRecord, AcceptanceRequest } from "../types";

type Props = {
  requests: AcceptanceRequest[];
  recordFor: (requestId: string) => AcceptanceRecord | undefined;
  onStartRecord: (request: AcceptanceRequest) => void;
};

export default function RecordSelector({
  requests,
  recordFor,
  onStartRecord,
}: Props) {
  return (
    <section className="rounded-xl bg-white p-4 shadow-sm">
      <h2 className="mb-2 font-semibold">Chọn PYC để lập BBNT</h2>
      {requests.length === 0 && <p className="text-sm text-slate-500">Chưa có PYC.</p>}
      <ul className="divide-y">
        {requests.map((request) => {
          const record = recordFor(request.id);
          return (
            <li key={request.id} className="flex items-center gap-2 py-3">
              <span className="flex-1">{recordPickerLabel(request, record)}</span>
              <button
                type="button"
                onClick={() => onStartRecord(request)}
                className="rounded border border-teal-700 px-3 py-2 text-sm text-teal-800"
              >
                {recordPickerActionLabel(record)}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
