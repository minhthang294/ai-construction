import type { Dispatch, SetStateAction } from "react";
import { downloadExport, exportRecord, exportRequest } from "../lib/api";
import { errorMessage } from "./acceptancePageModel";
import type { AcceptanceExport, AcceptanceRequest } from "../types";

type Options = {
  projectId: string;
  draftId?: string | null;
  setLastExport: Dispatch<SetStateAction<AcceptanceExport | null>>;
  setDownloadFailed: Dispatch<SetStateAction<boolean>>;
  setBusy: Dispatch<SetStateAction<boolean>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setMessage: Dispatch<SetStateAction<string | null>>;
};

export function useAcceptanceExport({
  projectId,
  draftId,
  setLastExport,
  setDownloadFailed,
  setBusy,
  setError,
  setMessage,
}: Options) {
  async function handleExportRequest(
    request: AcceptanceRequest,
    format: "xlsx" | "pdf",
  ) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const exported = await exportRequest(projectId, request.id, format);
      setLastExport(exported);
      try {
        const filename = await downloadExport(exported);
        setDownloadFailed(false);
        setMessage(
          `Đã xuất và tải ${filename}. Chỉ các ô đã kiểm tra được ghi.`,
        );
      } catch (downloadError) {
        setDownloadFailed(true);
        setError(
          `${errorMessage(downloadError)} File ${format.toUpperCase()} PYC ${request.number} đã tạo nhưng chưa tải được; bấm "Tải lại" bên dưới.`,
        );
      }
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function handleExportRecord(kind: "pyc" | "bbnt", format: "xlsx" | "pdf") {
    if (!draftId) {
      setError("Cần lưu BBNT trước khi xuất.");
      return;
    }
    const recordId = draftId;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const exported = await exportRecord(projectId, recordId, kind, format);
      setLastExport(exported);
      try {
        const filename = await downloadExport(exported);
        setDownloadFailed(false);
        setMessage(
          kind === "bbnt"
            ? `Đã xuất và tải ${filename}. Bản xuất dùng dữ liệu đã được con người xác nhận.`
            : `Đã xuất và tải ${filename}. Sheet BBNT được để trống an toàn.`,
        );
      } catch (downloadError) {
        setDownloadFailed(true);
        setError(
          `${errorMessage(downloadError)} File ${format.toUpperCase()} ${kind.toUpperCase()} đã tạo nhưng chưa tải được; bấm "Tải lại" bên dưới.`,
        );
      }
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function handleDownloadExport(exported: AcceptanceExport) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const filename = await downloadExport(exported);
      setDownloadFailed(false);
      setMessage(`Đã tải ${filename}.`);
    } catch (cause) {
      setDownloadFailed(true);
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return {
    handleExportRequest,
    handleExportRecord,
    handleDownloadExport,
  };
}
