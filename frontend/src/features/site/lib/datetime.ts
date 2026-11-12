/** Vietnam has a fixed UTC+7 offset (no daylight saving). */
const VN_OFFSET_MS = 7 * 60 * 60 * 1000;

/** Convert an ISO-8601 timestamp to an Asia/Ho_Chi_Minh `datetime-local` value. */
export function toLocalInputValue(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const shifted = new Date(date.getTime() + VN_OFFSET_MS);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(
    shifted.getUTCDate(),
  )}T${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}`;
}

/** Convert an Asia/Ho_Chi_Minh `datetime-local` value to a UTC ISO string. */
export function fromLocalInputValue(value: string): string | null {
  if (!value) return null;
  // Attach the fixed Vietnam offset instead of relying on the device timezone.
  const date = new Date(`${value}:00+07:00`);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

/** Format an ISO calendar date (`YYYY-MM-DD`) as Vietnamese `DD/MM/YYYY`. */
export function formatISODate(value?: string | null): string {
  if (!value) return "";
  const parts = value.split("-");
  if (parts.length !== 3 || parts.some((part) => !part)) return value;
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
}

/** Add days to a `YYYY-MM-DD` date without drifting through UTC. */
export function addDaysISO(value: string, days: number): string {
  const parts = value.split("-").map(Number);
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) return value;
  const date = new Date(parts[0], parts[1] - 1, parts[2] + days);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}
