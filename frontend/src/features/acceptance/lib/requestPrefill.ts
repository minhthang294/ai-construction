import type {
  AcceptanceRequest,
  FieldKind,
  ProjectContext,
  Urgency,
} from "../types";
import { projectMetadataDefaults } from "./projectPrefill";

/** Values safe to reuse from the previous PYC. */
export type RequestDefaults = {
  project_name: string;
  client: string;
  project_location: string;
  location: string;
  request_date: string;
  field: FieldKind | "";
  urgency: Urgency | "";
  requested_by_profile_id: string;
  supervisor_profile_id: string;
  investor_profile_id: string;
  requested_by_name: string;
  supervisor_name: string;
  investor_name: string;
  contractor_org: string;
  supervisor_org: string;
  investor_org: string;
};

export function todayIso(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

function text(value?: string | null): string {
  return (value ?? "").trim();
}

/** Latest submitted PYC, falling back to the latest saved draft. */
export function latestRequestForPrefill(
  requests: AcceptanceRequest[],
): AcceptanceRequest | null {
  const ordered = [...requests].sort((left, right) => {
    const leftKey = left.requested_at || left.updated_at || left.created_at;
    const rightKey = right.requested_at || right.updated_at || right.created_at;
    return rightKey.localeCompare(leftKey);
  });
  return ordered.find((request) => request.status === "submitted") ?? ordered[0] ?? null;
}

/**
 * Build defaults for a new PYC.
 *
 * Project identity fields follow current project setup. Request-specific
 * header/organisation fields come from the previous PYC, while content,
 * number, linked report and date are deliberately reset.
 */
export function buildRequestDefaults(
  previous?: AcceptanceRequest | null,
  project?: ProjectContext | null,
  today = todayIso(),
): RequestDefaults {
  const metadata = projectMetadataDefaults(project);
  return {
    project_name: metadata.project_name,
    client: metadata.client,
    project_location: metadata.project_location,
    location: text(previous?.location),
    request_date: today,
    field: previous?.field ?? "",
    urgency: previous?.urgency ?? "normal",
    requested_by_profile_id: text(previous?.requested_by_profile_id),
    supervisor_profile_id: text(previous?.supervisor_profile_id),
    investor_profile_id: text(previous?.investor_profile_id),
    requested_by_name: text(previous?.requested_by_name),
    supervisor_name: text(previous?.supervisor_name),
    investor_name: text(previous?.investor_name),
    contractor_org: text(previous?.contractor_org),
    supervisor_org: text(previous?.supervisor_org),
    investor_org: text(previous?.investor_org) || metadata.investor_org,
  };
}
