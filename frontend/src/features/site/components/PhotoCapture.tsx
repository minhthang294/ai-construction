import { useEffect, useRef, useState } from "react";
import {
  fetchPhotoObjectUrl,
  patchPhoto,
  uploadPhotos,
} from "../lib/api";
import { enqueue, photoQueueId } from "../lib/offlineDb";
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
};

type QueuedPreview = { id: string; url: string; name: string };

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
  onPatched,
}: {
  projectId: string;
  photo: SitePhoto;
  onPatched: (photo: SitePhoto) => void;
}) {
  const [caption, setCaption] = useState(photo.confirmed_caption ?? "");
  const [category, setCategory] = useState(photo.category ?? "");
  const [location, setLocation] = useState(photo.location ?? "");
  const [component, setComponent] = useState(photo.component ?? "");
  const [stage, setStage] = useState(photo.stage ?? "");
  const [saving, setSaving] = useState(false);
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
    } catch (error) {
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
            disabled={saving}
            onClick={() => void saveCaption()}
          >
            Lưu chú thích
          </button>
          <button
            type="button"
            className="min-h-9 flex-1 rounded-lg bg-gray-700 px-2 text-xs font-medium text-white disabled:opacity-50"
            disabled={saving}
            onClick={() => void saveMetadata()}
          >
            Lưu vị trí
          </button>
          <button
            type="button"
            className="min-h-9 rounded-lg border border-gray-300 px-2 text-xs"
            onClick={() => void downloadOriginal()}
          >
            Ảnh gốc
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
}: Props) {
  const [category, setCategory] = useState("");
  const [workItemId, setWorkItemId] = useState("");
  const [location, setLocation] = useState("");
  const [component, setComponent] = useState("");
  const [stage, setStage] = useState("");
  const [filterDraft, setFilterDraft] = useState<PhotoFilters>(filters);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [queuedPreviews, setQueuedPreviews] = useState<QueuedPreview[]>([]);
  const previewUrls = useRef<string[]>([]);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setFilterDraft(filters);
  }, [filters]);

  useEffect(() => {
    return () => {
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

  async function queueFiles(files: File[], ids: string[]) {
    for (const [index, file] of files.entries()) {
      const bytes = await file.arrayBuffer();
      const id = ids[index];
      await enqueue({
        id,
        projectId,
        kind: "photo",
        payload: {
          bytes,
          filename: file.name || "photo.jpg",
          type: file.type || "image/jpeg",
          reportId: reportId ?? null,
          reportDate: reportDate ?? null,
          category: category || null,
          location: location.trim() || null,
          component: component.trim() || null,
          stage: stage || null,
        },
        createdAt: Date.now(),
        attempts: 0,
      });
      const url = URL.createObjectURL(file);
      previewUrls.current.push(url);
      setQueuedPreviews((previous) => [...previous, { id, url, name: file.name }]);
    }
    onQueued?.();
  }

  async function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    // Generate the idempotency ids before the request.  If the response is lost
    // after the server saved the photo, the queued retry reuses the same id.
    const clientIds = files.map(() => photoQueueId());
    setBusy(true);
    setMessage(null);
    try {
      if (!online) {
        await queueFiles(files, clientIds);
        setMessage("Đã lưu ảnh vào hàng đợi, sẽ tải lên khi có mạng.");
        return;
      }
      const uploaded = await uploadPhotos(projectId, files, {
        reportId: reportId ?? undefined,
        category: category || undefined,
        location: location.trim() || undefined,
        component: component.trim() || undefined,
        stage: stage || undefined,
        workItemIds: workItemId ? [workItemId] : undefined,
        clientUploadIds: clientIds,
      });
      onUploaded(uploaded);
      setMessage(
        reportId
          ? `Đã tải ${uploaded.length} ảnh.`
          : `Đã tải ${uploaded.length} ảnh (chưa gắn báo cáo; lưu báo cáo rồi tải lại nếu cần).`,
      );
    } catch {
      // Network failure despite navigator.onLine: keep the originals queued
      // with the same idempotency ids used by the failed request.
      await queueFiles(files, clientIds);
      setMessage("Mất kết nối khi tải ảnh. Đã xếp hàng để thử lại.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-lg font-semibold">Ảnh hiện trường</h3>
        <p className="text-xs text-gray-500">
          Ảnh gốc được giữ nguyên. Ảnh chỉ vào báo cáo xuất khi có chú thích hoặc phân
          loại do người dùng xác nhận.
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

      <label
        className={`flex min-h-24 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed bg-white p-4 text-center ${
          busy ? "border-gray-300 opacity-60" : "border-blue-400"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          capture="environment"
          multiple
          className="hidden"
          disabled={busy}
          onChange={(event) => void handleFiles(event.target.files)}
        />
        <span className="text-base font-medium text-blue-700">
          {busy ? "Đang xử lý…" : "Chụp / chọn ảnh"}
        </span>
        <span className="text-xs text-gray-500">Hỗ trợ nhiều ảnh, lưu offline</span>
      </label>

      {message && <p className="rounded-lg bg-white p-3 text-sm shadow-sm">{message}</p>}

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
            onPatched={(updated) =>
              onUploaded([updated])
            }
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
