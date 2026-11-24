import { useEffect, useState } from "react";
import { fetchRequestPreviewImage, previewRecord, previewRequest } from "../lib/api";
import { errorMessage } from "./acceptancePageModel";
import type { AcceptanceRequest, PreviewPayload } from "../types";

type Options = {
  projectId: string;
  setError: (value: string | null) => void;
};

export function useAcceptancePreview({ projectId, setError }: Options) {
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);

  useEffect(() => {
    if (!previewImageUrl) return;
    return () => URL.revokeObjectURL(previewImageUrl);
  }, [previewImageUrl]);

  function closePreview() {
    setPreview(null);
    setPreviewImageUrl(null);
  }

  async function previewRequestById(request: AcceptanceRequest) {
    setError(null);
    setPreviewBusy(true);
    closePreview();
    try {
      const data = await previewRequest(projectId, request.id);
      setPreview(data);
      try {
        const imageUrl = await fetchRequestPreviewImage(projectId, request.id);
        setPreviewImageUrl(imageUrl);
      } catch (cause) {
        setError(
          cause instanceof Error
            ? cause.message
            : "Không tạo được ảnh xem trước PYC.",
        );
      }
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPreviewBusy(false);
    }
  }

  async function previewRecordById(recordId: string | null | undefined) {
    if (!recordId) {
      setError("Cần lưu BBNT trước khi xem trước.");
      return;
    }
    setError(null);
    closePreview();
    try {
      setPreview(await previewRecord(projectId, recordId));
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  return {
    preview,
    previewImageUrl,
    previewBusy,
    closePreview,
    previewRequestById,
    previewRecordById,
  };
}
