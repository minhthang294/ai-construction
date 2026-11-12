export type ExtractionScope = {
  projectId: string;
  documentId: string;
  pageNumber: number;
};

export type ExtractionScopeFields = {
  project_id?: string | null;
  document_id?: string | null;
  page_number?: number | null;
};

export function extractionScopeKey(
  projectId: string,
  documentId: string,
  pageNumber: number,
): string {
  return `${projectId}|${documentId}|${pageNumber}`;
}

export function isExtractionInScope(
  row: ExtractionScopeFields,
  projectId: string,
  documentId: string,
  pageNumber: number,
): boolean {
  return (
    row.project_id === projectId &&
    row.document_id === documentId &&
    row.page_number === pageNumber
  );
}

export function isStaleExtractionResponse(
  requestId: number,
  activeRequestId: number,
): boolean {
  return requestId !== activeRequestId;
}
