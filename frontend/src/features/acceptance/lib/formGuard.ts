export type AcceptanceTab = "requests" | "records";

export type GuardSnapshot = {
  tab: AcceptanceTab;
  requestDirty: boolean;
  recordDirty: boolean;
  hasEditingRequest: boolean;
  hasDraft: boolean;
};

export type GuardTarget =
  | { type: "switch-tab"; tab: AcceptanceTab }
  | { type: "close-request" }
  | { type: "close-record" }
  | { type: "edit-request" };

export const DISCARD_MESSAGE =
  "Bạn có thay đổi chưa lưu. Bỏ các thay đổi này và tiếp tục?";

/**
 * True only when the requested in-module navigation would discard unsaved
 * PYC/BBNT input. Nothing is stored in localStorage.
 */
export function requiresDiscardConfirmation(
  snapshot: GuardSnapshot,
  target: GuardTarget,
): boolean {
  switch (target.type) {
    case "switch-tab":
      if (target.tab === snapshot.tab) return false;
      return snapshot.tab === "requests"
        ? snapshot.hasEditingRequest && snapshot.requestDirty
        : snapshot.hasDraft && snapshot.recordDirty;
    case "close-request":
      return snapshot.hasEditingRequest && snapshot.requestDirty;
    case "close-record":
      return snapshot.hasDraft && snapshot.recordDirty;
    case "edit-request":
      return snapshot.hasEditingRequest && snapshot.requestDirty;
    default:
      return false;
  }
}

/** Revisions are only offered when the record is confirmed or stale. */
export function shouldOfferRevision(
  status: "draft" | "confirmed",
  stale: boolean,
): boolean {
  return stale || status === "confirmed";
}

/**
 * Dirty must survive an explicit failed save. Callers return false on failure;
 * legacy callers returning void are treated as successful.
 */
export function shouldMarkSaved(result: boolean | void): boolean {
  return result !== false;
}
