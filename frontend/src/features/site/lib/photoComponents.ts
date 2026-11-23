import { listComponentProgress } from "./api";

export type PhotoComponentOption = {
  id: string;
  code: string;
  zone: string;
  segment: number;
  eventStamp: string;
};

/** Components in the selected batch, newest progress first. */
export async function loadPhotoComponentOptions(
  projectId: string,
  batchId?: string | null,
): Promise<PhotoComponentOption[]> {
  const rows = await listComponentProgress(projectId, undefined, batchId || undefined);
  return rows
    .map((row) => {
      const event = row.construction_event;
      return {
        id: row.id,
        code: row.canonical_code,
        zone: row.zone,
        segment: row.segment_number,
        eventStamp: event ? `${event.event_date}T${event.created_at}` : "",
      };
    })
    .sort(
      (left, right) =>
        right.eventStamp.localeCompare(left.eventStamp) ||
        left.code.localeCompare(right.code),
    );
}
