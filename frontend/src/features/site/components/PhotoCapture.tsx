import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  deletePhoto,
  fetchPhotoObjectUrl,
  patchPhoto,
  uploadPhotos,
} from "../lib/api";
import { enqueue, photoQueueId } from "../lib/offlineDb";
import {
  formatPhotoBytes,
  getCurrentGpsPosition,
  PhotoProcessingError,
  photoFileSupport,
  photoLocationSourceLabel,
  photoLocationValue,
  photoTimeSourceLabel,
  photoTimeValue,
  preparePhotoForUpload,
} from "../lib/photoProcessing";
import type { LocationFix, PhotoWatermarkInfo, PhotoSource } from "../lib/photoProcessing";
import {
  EMPTY_PHOTO_FILTERS,
  PHOTO_CATEGORIES,
  PHOTO_STAGES,
  photoCategoryLabel,
  photoStageLabel,
} from "../types";
import type { PhotoFilters, SitePhoto, WorkItem } from "../types";

type Props = {
  projectId: string;
  reportId?: string | null;
  reportDate?: string | null;
  photos: SitePhoto[];
  online: boolean;
  pendingCount?: number;
  workItems?: WorkItem[];
  filters: PhotoFilters;
  onFiltersChange: (filters: PhotoFilters) => void;
  onUploaded: (photos: SitePhoto[]) => void;
  onQueued?: () => void;
  onDeleted?: (photoId: string) => void;
};

type QueuedPreview = { id: string; url: string; name: string };

type PreparedPreview = {
  id: string;
  url: string;
  info: PhotoWatermarkInfo;
} & {
  file: File;
  width: number;
  height: number;
  bytes: number;
  quality: number;
  overTarget: boolean;
};

function AuthenticatedImage({ projectId, photo }: { projectId: string; photo: SitePhoto }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | null = null;
    fetchPhotoObjectUrl(projectId, photo.id, controller.signal)
      .then((value) => {
        objectUrl = value;
        setUrl(value);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [projectId, photo.id]);

  if (failed) {
    return (
      <div className="flex h-32 items-center justify-center bg-gray-100 text-xs text-gray-500">
        Không tải được ảnh
      </div>
    );
  }
  if (!url) {
    return <div className="h-32 animate-pulse bg-gray-100" />;
  }
  return (
    <img
      src={url}
      alt={photo.confirmed_caption || photo.category || photo.filename || photo.id}
      className="h-32 w-full object-cover"
    />
  );
}

function PhotoCard({
  projectId,
  photo,
  online,
  onPatched,
  onDeleted,
}: {
  projectId: string;
  photo: SitePhoto;
  online: boolean;
  onPatched: (photo: SitePhoto) => void;
  onDeleted: (photoId: string) => void;
}) {
  const [caption, setCaption] = useState(photo.confirmed_caption ?? "");
  const [category, setCategory] = useState(photo.category ?? "");
  const [location, setLocation] = useState(photo.location ?? "");
  const [component, setComponent] = useState(photo.component ?? "");
  const [stage, setStage] = useState(photo.stage ?? "");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setCaption(photo.confirmed_caption ?? "");
    setCategory(photo.category ?? "");
    setLocation(photo.location ?? "");
    setComponent(photo.component ?? "");
    setStage(photo.stage ?? "");
  }, [
    photo.confirmed_caption,
    photo.category,
    photo.location,
    photo.component,
    photo.stage,
  ]);

  const confirmed = Boolean(caption.trim() || category);

  async function saveCaption() {
    setSaving(true);
    setMessage(null);
    try {
      const updated = await patchPhoto(projectId, photo.id, {
        confirmed_caption: caption.trim() || null,
      });
      onPatched(updated);
      setMessage("Đã xác nhận chú thích.");
    } catch {
      setMessage("Không lưu được chú thích.");
    } finally {
      setSaving(false);
    }
  }

  async function saveCategory(value: string) {
    setCategory(value);
    setSaving(true);
    setMessage(null);
    try {
      const updated = await patchPhoto(projectId, photo.id, {
        category: value || null,
      });
      onPatched(updated);
    } catch {
      setMessage("Không lưu được phân loại.");
      setCategory(photo.category ?? "");
    } finally {
      setSaving(false);
    }
  }

  async function saveMetadata() {
    setSaving(true);
    setMessage(null);
    try {
      const updated = await patchPhoto(projectId, photo.id, {
        location: location.trim() || null,
        component: component.trim() || null,
        stage: stage || null,
      });
      onPatched(updated);
      setMessage("Đã lưu vị trí/hạng mục/giai đoạn.");
    } catch {
      setMessage("Không lưu được vị trí/hạng mục/giai đoạn.");
    } finally {
      setSaving(false);
    }
  }

  async function downloadOriginal() {
    try {
      const url = await fetchPhotoObjectUrl(projectId, photo.id);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = photo.filename || `${photo.id}.jpg`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch {
      setMessage("Không tải được ảnh gốc.");
    }
  }

  async function removePhoto() {
    if (!online) {
      setMessage("Cần kết nối mạng để xóa ảnh.");
      return;
    }
    if (
      !window.confirm(
        "Xóa ảnh này khỏi máy chủ? Ảnh đã dùng làm bằng chứng sẽ không xóa được.",
      )
    ) {
      return;
    }
    setDeleting(true);
    setMessage(null);
    try {
      await deletePhoto(projectId, photo.id);
      onDeleted(photo.id);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setMessage(
          "Ảnh đang được dùng làm bằng chứng (tiến độ/nhật ký/nghiệm thu); không thể xóa.",
        );
      } else if (error instanceof ApiError && error.status === 404) {
        setMessage("Ảnh không còn trên máy chủ; đã làm mới danh sách.");
        onDeleted(photo.id);
      } else {
        setMessage("Không xóa được ảnh.");
      }
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <AuthenticatedImage projectId={projectId} photo={photo} />
      <div className="space-y-2 p-2 text-xs">
        <div className="flex items-center justify-between gap-2 text-gray-500">
          <span>{photoCategoryLabel(category)}</span>
          <span className={confirmed ? "text-green-700" : "text-amber-700"}>
            {confirmed ? "Đã xác nhận" : "Chưa xác nhận"}
          </span>
        </div>
        <p className="text-gray-500">
          {location || "Chưa có vị trí"} · {component || "Chưa có hạng mục"} ·{" "}
          {photoStageLabel(stage)}
        </p>
        <input
          className="min-h-10 w-full rounded-lg border border-gray-300 px-2 text-sm"
          placeholder="Chú thích xác nhận"
          value={caption}
          onChange={(event) => setCaption(event.target.value)}
        />
        <select
          className="min-h-10 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm"
          value={category}
          disabled={saving}
          onChange={(event) => void saveCategory(event.target.value)}
        >
          <option value="">Chưa phân loại</option>
          {PHOTO_CATEGORIES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <input
          className="min-h-9 w-full rounded-lg border border-gray-300 px-2 text-sm"
          placeholder="Vị trí (vd: Trụ T1)"
          value={location}
          onChange={(event) => setLocation(event.target.value)}
        />
        <input
          className="min-h-9 w-full rounded-lg border border-gray-300 px-2 text-sm"
          placeholder="Hạng mục (vd: Bê tông)"
          value={component}
          onChange={(event) => setComponent(event.target.value)}
        />
        <select
          className="min-h-9 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm"
          value={stage}
          onChange={(event) => setStage(event.target.value)}
        >
          <option value="">Chưa phân giai đoạn</option>
          {PHOTO_STAGES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="min-h-9 flex-1 rounded-lg bg-gray-800 px-2 text-xs font-medium text-white disabled:opacity-50"
            disabled={saving || deleting}
            onClick={() => void saveCaption()}
          >
            Lưu chú thích
          </button>
          <button
            type="button"
            className="min-h-9 flex-1 rounded-lg bg-gray-700 px-2 text-xs font-medium text-white disabled:opacity-50"
            disabled={saving || deleting}
            onClick={() => void saveMetadata()}
          >
            Lưu vị trí
          </button>
          <button
            type="button"
            className="min-h-9 rounded-lg border border-gray-300 px-2 text-xs"
            disabled={deleting}
            onClick={() => void downloadOriginal()}
          >
            Ảnh gốc
          </button>
          <button
            type="button"
            className="min-h-9 rounded-lg border border-red-200 px-2 text-xs text-red-700 disabled:opacity-50"
            disabled={deleting}
            onClick={() => void removePhoto()}
          >
            {deleting ? "Đang xóa…" : "Xóa ảnh"}
          </button>
        </div>
        {photo.gps_lat != null && photo.gps_lon != null && (
          <p className="text-gray-500">
            GPS EXIF: {photo.gps_lat.toFixed(5)}, {photo.gps_lon.toFixed(5)} (chưa xác nhận)
          </p>
        )}
        {message && <p className="text-gray-600">{message}</p>}
      </div>
    </div>
  );
}

export default function PhotoCapture({
  projectId,
  reportId,
  reportDate,
  photos,
  online,
  pendingCount = 0,
  workItems = [],
  filters,
  onFiltersChange,
  onUploaded,
  onQueued,
  onDeleted,
}: Props) {
  const [category, setCategory] = useState("");
  const [workItemId, setWorkItemId] = useState("");
  const [location, setLocation] = useState("");
  const [component, setComponent] = useState("");
  const [stage, setStage] = useState("");
  const [filterDraft, setFilterDraft] = useState<PhotoFilters>(filters);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [prepared, setPrepared] = useState<PreparedPreview[]>([]);
  const [queuedPreviews, setQueuedPreviews] = useState<QueuedPreview[]>([]);
  const preparedUrls = useRef<string[]>([]);
  const previewUrls = useRef<string[]>([]);
  const cameraRef = useRef<HTMLInputElement | null>(null);
  const galleryRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setFilterDraft(filters);
  }, [filters]);

  useEffect(() => {
    return () => {
      preparedUrls.current.forEach((url) => URL.revokeObjectURL(url));
      previewUrls.current.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  useEffect(() => {
    if (online && pendingCount === 0 && queuedPreviews.length > 0) {
      queuedPreviews.forEach((preview) => URL.revokeObjectURL(preview.url));
      previewUrls.current = [];
      setQueuedPreviews([]);
    }
  }, [online, pendingCount, queuedPreviews]);

  function releasePrepared(items: PreparedPreview[]) {
    const urls = new Set(items.map((item) => item.url));
    items.forEach((item) => URL.revokeObjectURL(item.url));
    preparedUrls.current = preparedUrls.current.filter((url) => !urls.has(url));
    const ids = new Set(items.map((item) => item.id));
    setPrepared((previous) => previous.filter((item) => !ids.has(item.id)));
  }

  function removePrepared(id: string) {
    const item = prepared.find((entry) => entry.id === id);
    if (item) releasePrepared([item]);
  }

  function clearPrepared() {
    releasePrepared(prepared);
  }

  async function queuePrepared(items: PreparedPreview[]) {
    for (const [index, item] of items.entries()) {
      const bytes = await item.file.arrayBuffer();
      await enqueue({
        id: item.id,
        projectId,
        kind: "photo",
        payload: {
          bytes,
          // Queue the actual watermarked JPEG, not the original file.
          filename: item.file.name || "photo.jpg",
          type: item.file.type || "image/jpeg",
          reportId: reportId ?? null,
          reportDate: reportDate ?? null,
          category: category || null,
          location: location.trim() || null,
          component: component.trim() || null,
          stage: stage || null,
          workItemIds: workItemId ? [workItemId] : null,
        },
        createdAt: Date.now() + index,
        attempts: 0,
      });
      const url = URL.createObjectURL(item.file);
      previewUrls.current.push(url);
      setQueuedPreviews((previous) => [
        ...previous,
        { id: item.id, url, name: item.file.name },
      ]);
    }
  }

  async function handleFiles(fileList: FileList | null, source: PhotoSource) {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    const capturedAt = source === "camera" ? new Date() : undefined;
    setBusy(true);
    setMessage(null);
    const errors: string[] = [];
    try {
      let deviceGps: LocationFix | null = null;
      if (source === "camera") {
        setMessage("Đang lấy vị trí GPS (nếu được phép)…");
        deviceGps = await getCurrentGpsPosition();
      }
      const next: PreparedPreview[] = [];
      for (const file of files) {
        const support = photoFileSupport(file);
        if (!support.ok) {
          errors.push(`${file.name}: ${support.reason}`);
          continue;
        }
        try {
          const result = await preparePhotoForUpload(file, {
            source,
            capturedAt,
            enteredLocation: location,
            deviceGps,
          });
          const url = URL.createObjectURL(result.file);
          preparedUrls.current.push(url);
          next.push({ id: photoQueueId(), url, ...result });
        } catch (error) {
          const reason =
            error instanceof PhotoProcessingError
              ? error.message
              : "Không đọc được ảnh trên trình duyệt này (có thể là HEIC/HEIF). Hãy chọn ảnh JPEG/PNG hoặc chuyển định dạng rồi thử lại.";
          errors.push(`${file.name}: ${reason}`);
        }
      }
      if (next.length > 0) {
        setPrepared((previous) => [...previous, ...next]);
      }
      if (errors.length > 0) {
        setMessage(errors.join(" "));
      } else if (next.length > 0) {
        setMessage(
          `Đã xử lý ${next.length} ảnh. Kiểm tra ngày giờ/vị trí rồi tải lên.`,
        );
      }
    } finally {
      setBusy(false);
      if (cameraRef.current) cameraRef.current.value = "";
      if (galleryRef.current) galleryRef.current.value = "";
    }
  }

  async function uploadPrepared() {
    const items = prepared;
    if (items.length === 0) return;
    setBusy(true);
    setMessage(null);
    try {
      if (!online) {
        try {
          await queuePrepared(items);
          clearPrepared();
          setMessage("Đã lưu ảnh đã xử lý vào hàng đợi, sẽ tải lên khi có mạng.");
          onQueued?.();
        } catch {
          setMessage(
            "Không lưu được hàng đợi offline trên thiết bị này. Ảnh vẫn đang chờ để thử lại.",
          );
        }
        return;
      }

      try {
        const uploaded = await uploadPhotos(
          projectId,
          items.map((item) => item.file),
          {
            reportId: reportId ?? undefined,
            category: category || undefined,
            location: location.trim() || undefined,
            component: component.trim() || undefined,
            stage: stage || undefined,
            workItemIds: workItemId ? [workItemId] : undefined,
            clientUploadIds: items.map((item) => item.id),
          },
        );
        onUploaded(uploaded);
        clearPrepared();
        setMessage(
          reportId
            ? `Đã tải ${uploaded.length} ảnh.`
            : `Đã tải ${uploaded.length} ảnh (chưa gắn báo cáo; lưu báo cáo rồi tải lại nếu cần).`,
        );
      } catch (error) {
        if (error instanceof ApiError && error.status < 500) {
          setMessage(error.message);
          return;
        }
        // Network failure despite navigator.onLine: keep the processed bytes
        // queued with the same idempotency ids used by the failed request.
        try {
          await queuePrepared(items);
          clearPrepared();
          setMessage("Mất kết nối khi tải ảnh. Đã xếp hàng ảnh đã xử lý để thử lại.");
          onQueued?.();
        } catch {
          setMessage(
            "Mất kết nối và không lưu được hàng đợi offline. Ảnh vẫn đang chờ để thử lại.",
          );
        }
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-lg font-semibold">Ảnh hiện trường</h3>
        <p className="text-xs text-gray-500">
          Ảnh tải lên được in ngày giờ/vị trí, xoay đúng hướng, thu cạnh dài về
          1.920 px và nén JPEG mục tiêu 500 KB. Ảnh chỉ vào báo cáo xuất khi có
          chú thích hoặc phân loại do người dùng xác nhận.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <select
          className="min-h-11 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          <option value="">Chưa phân loại (không vào báo cáo)</option>
          {PHOTO_CATEGORIES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <select
          className="min-h-11 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm"
          value={workItemId}
          onChange={(event) => setWorkItemId(event.target.value)}
        >
          <option value="">Gắn công việc (tuỳ chọn)</option>
          {workItems.map((item) => (
            <option key={item.id} value={item.id}>
              {item.code}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <input
          className="min-h-11 w-full rounded-lg border border-gray-300 px-2 text-sm"
          placeholder="Vị trí ảnh (vd: Trụ T1)"
          value={location}
          disabled={busy || prepared.length > 0}
          onChange={(event) => setLocation(event.target.value)}
        />
        <input
          className="min-h-11 w-full rounded-lg border border-gray-300 px-2 text-sm"
          placeholder="Hạng mục (vd: Bê tông)"
          value={component}
          onChange={(event) => setComponent(event.target.value)}
        />
        <select
          className="min-h-11 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm"
          value={stage}
          onChange={(event) => setStage(event.target.value)}
        >
          <option value="">Chưa phân giai đoạn</option>
          {PHOTO_STAGES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="min-h-11 rounded-lg border border-gray-300 text-xs"
          disabled={busy || prepared.length > 0}
          onClick={() => {
            setLocation("");
            setComponent("");
            setStage("");
            setCategory("");
            setWorkItemId("");
          }}
        >
          Xoá metadata
        </button>
      </div>
      <p className="text-xs text-gray-500">
        Nhập vị trí trước khi chụp/chọn ảnh nếu muốn in vị trí đó lên ảnh. Ảnh
        chọn từ máy không có EXIF sẽ ghi “Chưa xác định”, không tự lấy vị trí hiện tại.
      </p>

      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          className="min-h-12 rounded-xl border-2 border-blue-400 bg-white px-3 text-sm font-medium text-blue-700 disabled:opacity-60"
          disabled={busy}
          onClick={() => cameraRef.current?.click()}
        >
          Chụp ảnh
        </button>
        <button
          type="button"
          className="min-h-12 rounded-xl border-2 border-blue-400 bg-white px-3 text-sm font-medium text-blue-700 disabled:opacity-60"
          disabled={busy}
          onClick={() => galleryRef.current?.click()}
        >
          Chọn ảnh từ máy
        </button>
      </div>
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        disabled={busy}
        onChange={(event) => void handleFiles(event.target.files, "camera")}
      />
      <input
        ref={galleryRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        disabled={busy}
        onChange={(event) => void handleFiles(event.target.files, "gallery")}
      />

      {message && <p className="rounded-lg bg-white p-3 text-sm shadow-sm">{message}</p>}

      {prepared.length > 0 && (
        <div className="space-y-2 rounded-xl border border-blue-200 bg-blue-50 p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold text-blue-900">
              Ảnh đã xử lý ({prepared.length})
            </p>
            <button
              type="button"
              className="min-h-9 rounded-lg border border-blue-300 bg-white px-2 text-xs"
              disabled={busy}
              onClick={clearPrepared}
            >
              Bỏ tất cả
            </button>
          </div>
          <p className="text-xs text-blue-800">Để đổi vị trí in trên ảnh, bỏ ảnh xem trước rồi nhập vị trí và chọn lại ảnh.</p>
          <div className="grid grid-cols-2 gap-2">
            {prepared.map((item) => (
              <div
                key={item.id}
                className="overflow-hidden rounded-lg border border-gray-200 bg-white"
              >
                <img
                  src={item.url}
                  alt={item.file.name}
                  className="h-32 w-full object-cover"
                />
                <div className="space-y-1 p-2 text-xs">
                  <p className="font-medium">
                    Thời gian: {photoTimeValue(item.info)}
                  </p>
                  <p>Vị trí: {photoLocationValue(item.info)}</p>
                  <p className="text-gray-500">
                    Nguồn: {photoTimeSourceLabel(item.info)} ·{" "}
                    {photoLocationSourceLabel(item.info)}
                  </p>
                  <p className="text-gray-500">
                    {item.width}×{item.height} · {formatPhotoBytes(item.bytes)} · JPEG{" "}
                    {Math.round(item.quality * 100)}%
                  </p>
                  {item.overTarget && (
                    <p className="text-amber-700">
                      Vẫn trên 500 KB sau khi nén chất lượng tối thiểu; kiểm tra lại
                      ảnh.
                    </p>
                  )}
                  <button
                    type="button"
                    className="min-h-9 w-full rounded-lg border border-red-200 text-red-700"
                    disabled={busy}
                    onClick={() => removePrepared(item.id)}
                  >
                    Bỏ ảnh
                  </button>
                </div>
              </div>
            ))}
          </div>
          <button
            type="button"
            className="min-h-12 w-full rounded-xl bg-blue-600 text-sm font-semibold text-white disabled:opacity-60"
            disabled={busy}
            onClick={() => void uploadPrepared()}
          >
            {busy
              ? "Đang xử lý…"
              : online
                ? `Tải lên ${prepared.length} ảnh`
                : `Lưu ${prepared.length} ảnh vào hàng đợi`}
          </button>
        </div>
      )}

      <details className="rounded-xl bg-white p-3 shadow-sm">
        <summary className="cursor-pointer text-sm font-semibold">Lọc ảnh</summary>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <input
            type="date"
            className="min-h-10 w-full rounded-lg border border-gray-300 px-2 text-sm"
            value={filterDraft.date}
            onChange={(event) =>
              setFilterDraft({ ...filterDraft, date: event.target.value })
            }
          />
          <input
            className="min-h-10 w-full rounded-lg border border-gray-300 px-2 text-sm"
            placeholder="Vị trí"
            value={filterDraft.location}
            onChange={(event) =>
              setFilterDraft({ ...filterDraft, location: event.target.value })
            }
          />
          <input
            className="min-h-10 w-full rounded-lg border border-gray-300 px-2 text-sm"
            placeholder="Hạng mục"
            value={filterDraft.component}
            onChange={(event) =>
              setFilterDraft({ ...filterDraft, component: event.target.value })
            }
          />
          <select
            className="min-h-10 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm"
            value={filterDraft.stage}
            onChange={(event) =>
              setFilterDraft({ ...filterDraft, stage: event.target.value })
            }
          >
            <option value="">Mọi giai đoạn</option>
            {PHOTO_STAGES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <select
            className="min-h-10 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm"
            value={filterDraft.work_item_id}
            onChange={(event) =>
              setFilterDraft({ ...filterDraft, work_item_id: event.target.value })
            }
          >
            <option value="">Mọi công việc</option>
            {workItems.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} — {item.name}
              </option>
            ))}
          </select>
        </div>
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            className="min-h-9 flex-1 rounded-lg bg-blue-600 px-3 text-xs font-medium text-white"
            onClick={() => onFiltersChange(filterDraft)}
          >
            Áp dụng lọc
          </button>
          <button
            type="button"
            className="min-h-9 rounded-lg border border-gray-300 px-3 text-xs"
            onClick={() => {
              setFilterDraft(EMPTY_PHOTO_FILTERS);
              onFiltersChange(EMPTY_PHOTO_FILTERS);
            }}
          >
            Xoá lọc
          </button>
        </div>
      </details>

      {queuedPreviews.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="text-sm text-amber-800">
            {queuedPreviews.length} ảnh đang chờ đồng bộ
          </p>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {queuedPreviews.map((preview) => (
              <img
                key={preview.id}
                src={preview.url}
                alt={preview.name}
                className="h-20 w-full rounded object-cover"
              />
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        {photos.map((photo) => (
          <PhotoCard
            key={photo.id}
            projectId={projectId}
            photo={photo}
            online={online}
            onPatched={(updated) => onUploaded([updated])}
            onDeleted={(photoId) => onDeleted?.(photoId)}
          />
        ))}
      </div>
      {photos.length === 0 && (
        <p className="rounded-lg bg-gray-50 p-3 text-sm text-gray-500">
          Chưa có ảnh cho báo cáo này.
        </p>
      )}
    </section>
  );
}
