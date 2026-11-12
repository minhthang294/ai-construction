import type { ProjectContext } from "../types";

/** Repeated PYC/BBNT header values sourced from project setup. */
export type ProjectMetadataDefaults = {
  project_name: string;
  client: string;
  project_location: string;
  investor_org: string;
};

function text(value?: string | null): string {
  return (value ?? "").trim();
}

export function projectMetadataDefaults(
  project?: ProjectContext | null,
): ProjectMetadataDefaults {
  const client = text(project?.client);
  return {
    project_name: text(project?.name),
    client,
    project_location: text(project?.location),
    // In the Excel template the investor/client is the same organisation as
    // the "Đại diện Chủ đầu tư" line on the BBNT.  Users can still override it.
    investor_org: client,
  };
}

function keepOr(value: string | null | undefined, fallback: string): string {
  const current = text(value);
  return current || fallback;
}

/** Fill blank metadata only; explicit PYC-specific values are preserved. */
export function mergeProjectMetadata<T extends Partial<ProjectMetadataDefaults>>(
  values: T,
  project?: ProjectContext | null,
): T & ProjectMetadataDefaults {
  const defaults = projectMetadataDefaults(project);
  return {
    ...values,
    project_name: keepOr(values.project_name, defaults.project_name),
    client: keepOr(values.client, defaults.client),
    project_location: keepOr(values.project_location, defaults.project_location),
    investor_org: keepOr(values.investor_org, defaults.investor_org),
  };
}
