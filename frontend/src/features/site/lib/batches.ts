/** Construction batch ("Đợt thi công") types shared by site and app pages. */

export type ConstructionBatch = {
  id: string;
  name: string;
  note: string | null;
  archived: boolean;
  created_by: string;
  created_at: string;
  component_count: number;
  primary_zone: string | null;
};

export type BatchComponent = {
  id: string;
  type: "pile" | "beam";
  canonical_code: string;
  raw_code: string;
  segment_id: string;
  segment_number: number;
  zone: string;
  design_group: string | null;
  verification: string;
  reason?: string | null;
  added_at?: string;
};

export type ConstructionBatchDetail = ConstructionBatch & {
  components: BatchComponent[];
};

export type BatchPreviewCandidate = {
  id: string;
  type: "pile" | "beam";
  canonical_code: string;
  raw_code: string;
  segment_id: string;
  segment_number: number;
  zone: string;
  design_group: string | null;
  verification: string;
  in_batch: boolean;
};

export type BatchPreview = {
  codes: string[];
  matched: Array<{ code: string; component: BatchPreviewCandidate }>;
  ambiguous: Array<{ code: string; candidates: BatchPreviewCandidate[] }>;
  missing: string[];
  already_in_batch: string[];
};

export type ProgressEventRecord = {
  id: string;
  component_id: string;
  stage_id: string;
  event_date: string;
  status: "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED" | "BLOCKED";
  quantity: number | null;
  unit: string | null;
  note: string | null;
  evidence_refs: string[];
  batch_id: string | null;
  created_by: string | null;
  created_at: string;
};
