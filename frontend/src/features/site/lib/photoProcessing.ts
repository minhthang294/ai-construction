// Client-side photo preparation for site uploads: read the metadata we are
// allowed to trust, draw it onto the pixels, normalize orientation through the
// browser decoder, resize and compress to JPEG before upload/offline queue.

export const PHOTO_MAX_LONG_EDGE = 1920;
export const PHOTO_TARGET_BYTES = 500 * 1024;
export const JPEG_QUALITY_STEPS = [0.82, 0.77, 0.72, 0.67, 0.65] as const;

const SUPPORTED_MIME_TYPES = new Set([
  "image/jpeg",
  "image/jpg",
  "image/pjpeg",
  "image/png",
  "image/webp",
  "image/avif",
  "image/gif",
  "image/bmp",
  "image/tiff",
  "image/heic",
  "image/heif",
]);

const SUPPORTED_EXTENSIONS = new Set([
  "jpg",
  "jpeg",
  "png",
  "webp",
  "avif",
  "gif",
  "bmp",
  "tif",
  "tiff",
  "heic",
  "heif",
]);

export type LocationFix = {
  latitude: number;
  longitude: number;
};

export type PhotoTimeSource = "exif" | "camera" | "unknown";
export type PhotoGpsSource = "device" | "exif" | null;

export type PhotoWatermarkInfo = {
  capturedAt: Date | null;
  timeSource: PhotoTimeSource;
  /** Location text the user actually entered; never inferred from the project. */
  locationText: string | null;
  gps: LocationFix | null;
  gpsSource: PhotoGpsSource;
};

export type PhotoExifMetadata = {
  orientation: number | null;
  /** Raw EXIF wall-clock text; parsed only when a watermark is prepared. */
  captureTime: string | null;
  gps: LocationFix | null;
  device: string | null;
};

export type PhotoSource = "camera" | "gallery";

export type PreparePhotoOptions = {
  source: PhotoSource;
  capturedAt?: Date;
  enteredLocation?: string | null;
  /** Only used for a new camera capture; gallery photos never get a new fix. */
  deviceGps?: LocationFix | null;
};

export type PreparedPhoto = {
  file: File;
  width: number;
  height: number;
  bytes: number;
  quality: number;
  overTarget: boolean;
  info: PhotoWatermarkInfo;
};

export class PhotoProcessingError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PhotoProcessingError";
  }
}

function fileExtension(name: string): string {
  const match = /\.([^.]+)$/.exec(name || "");
  return match ? match[1].toLowerCase() : "";
}

export function photoFileSupport(file: File): { ok: true } | { ok: false; reason: string } {
  if (file.size === 0) {
    return { ok: false, reason: "Tệp rỗng." };
  }
  const type = (file.type || "").toLowerCase();
  const extension = fileExtension(file.name);
  const byMime = type === "" || SUPPORTED_MIME_TYPES.has(type);
  const byExtension = SUPPORTED_EXTENSIONS.has(extension);
  if (type === "image/svg+xml" || extension === "svg") {
    return {
      ok: false,
      reason: "Không hỗ trợ ảnh SVG. Hãy chọn ảnh JPEG, PNG hoặc WebP.",
    };
  }
  const genericType = type === "" || type === "application/octet-stream";
  if (byMime || (genericType && byExtension)) {
    return { ok: true };
  }
  return {
    ok: false,
    reason:
      "Định dạng ảnh không được hỗ trợ. Chọn JPEG, PNG, WebP, HEIC/HEIF, AVIF, GIF, BMP hoặc TIFF.",
  };
}

export function fitPhotoDimensions(
  width: number,
  height: number,
  maxLongEdge: number = PHOTO_MAX_LONG_EDGE,
): { width: number; height: number } {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return { width: 0, height: 0 };
  }
  const scale = Math.min(1, maxLongEdge / width, maxLongEdge / height);
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

export function parseExifDate(raw: string | null | undefined): Date | null {
  const match = /^(\d{4})[:\-](\d{2})[:\-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})/.exec(
    (raw ?? "").trim(),
  );
  if (!match) return null;
  const [, year, month, day, hour, minute, second] = match.map(Number);
  const date = new Date(year, month - 1, day, hour, minute, second);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day ||
    date.getHours() !== hour ||
    date.getMinutes() !== minute ||
    date.getSeconds() !== second
  ) {
    return null;
  }
  return date;
}

export function formatGps(gps: LocationFix): string {
  return `${gps.latitude.toFixed(5)}, ${gps.longitude.toFixed(5)}`;
}

export function formatPhotoDateTime(date: Date | null): string {
  if (!date || Number.isNaN(date.getTime())) return "Chưa xác định";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function formatPhotoBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "Chưa xác định";
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  return `${Math.round(bytes / 1024)} KB`;
}

/**
 * Resolve only values the capture actually provides. Gallery photos never get
 * the current time or current GPS; missing metadata stays "Chưa xác định".
 */
export function resolvePhotoWatermarkInfo(
  exif: PhotoExifMetadata | null,
  options: PreparePhotoOptions,
): PhotoWatermarkInfo {
  const exifTime = parseExifDate(exif?.captureTime);
  let capturedAt = exifTime;
  let timeSource: PhotoTimeSource = exifTime ? "exif" : "unknown";
  if (!capturedAt && options.source === "camera") {
    capturedAt = options.capturedAt ?? new Date();
    timeSource = "camera";
  }

  const deviceGps = options.source === "camera" ? options.deviceGps ?? null : null;
  const gps = deviceGps ?? exif?.gps ?? null;
  let gpsSource: PhotoGpsSource = null;
  if (gps) gpsSource = deviceGps ? "device" : "exif";

  return {
    capturedAt,
    timeSource,
    locationText: (options.enteredLocation ?? "").trim() || null,
    gps,
    gpsSource,
  };
}

export function photoTimeValue(info: PhotoWatermarkInfo): string {
  return formatPhotoDateTime(info.capturedAt);
}

export function photoLocationValue(info: PhotoWatermarkInfo): string {
  const parts = [info.locationText, info.gps ? formatGps(info.gps) : null].filter(
    (value): value is string => Boolean(value),
  );
  return parts.length > 0 ? parts.join(" • ") : "Chưa xác định";
}

export function photoTimeSourceLabel(info: PhotoWatermarkInfo): string {
  if (info.timeSource === "exif") return "EXIF";
  if (info.timeSource === "camera") return "Giờ thiết bị khi chụp";
  return "Chưa xác định";
}

export function photoLocationSourceLabel(info: PhotoWatermarkInfo): string {
  const parts: string[] = [];
  if (info.locationText) parts.push("Vị trí nhập");
  if (info.gps) {
    parts.push(info.gpsSource === "device" ? "GPS thiết bị" : "GPS trong ảnh");
  }
  return parts.length > 0 ? parts.join(" + ") : "Chưa xác định";
}

export function photoWatermarkLines(info: PhotoWatermarkInfo): [string, string] {
  return [
    `Thời gian: ${photoTimeValue(info)}`,
    `Vị trí: ${photoLocationValue(info)}`,
  ];
}

// ---------------------------------------------------------------------------
// EXIF reader (JPEG APP1 + TIFF). Best-effort only: malformed metadata is
// ignored rather than turned into a guessed value.
// ---------------------------------------------------------------------------

type IfdEntry = {
  tag: number;
  type: number;
  count: number;
  entryOffset: number;
  valueOffset: number;
};

const TAG_ORIENTATION = 0x0112;
const TAG_MAKE = 0x010f;
const TAG_MODEL = 0x0110;
const TAG_DATETIME = 0x0132;
const TAG_EXIF_IFD = 0x8769;
const TAG_GPS_IFD = 0x8825;
const TAG_DATETIME_ORIGINAL = 0x9003;
const TAG_DATETIME_DIGITIZED = 0x9004;

const GPS_LAT_REF = 0x0001;
const GPS_LAT = 0x0002;
const GPS_LON_REF = 0x0003;
const GPS_LON = 0x0004;

function typeSize(type: number): number {
  switch (type) {
    case 1:
    case 2:
    case 7:
      return 1;
    case 3:
      return 2;
    case 4:
    case 9:
      return 4;
    case 5:
    case 10:
      return 8;
    default:
      return 0;
  }
}

function readAscii(view: DataView, offset: number, count: number): string {
  let value = "";
  for (let index = 0; index < count; index += 1) {
    const code = view.getUint8(offset + index);
    if (code === 0) break;
    value += String.fromCharCode(code);
  }
  return value.trim();
}

function entryDataOffset(entry: IfdEntry, tiffStart: number): number {
  const size = typeSize(entry.type) * entry.count;
  return size <= 4 ? entry.entryOffset + 8 : tiffStart + entry.valueOffset;
}

function readUnsignedValue(
  view: DataView,
  entry: IfdEntry,
  tiffStart: number,
  littleEndian: boolean,
): number | null {
  const offset = entryDataOffset(entry, tiffStart);
  if (entry.type === 1) return view.getUint8(offset);
  if (entry.type === 3) return view.getUint16(offset, littleEndian);
  if (entry.type === 4) return view.getUint32(offset, littleEndian);
  return null;
}

function readAsciiEntry(
  view: DataView,
  entry: IfdEntry | undefined,
  tiffStart: number,
): string | null {
  if (!entry || entry.type !== 2) return null;
  const value = readAscii(view, entryDataOffset(entry, tiffStart), entry.count);
  return value || null;
}

function readRational(
  view: DataView,
  offset: number,
  littleEndian: boolean,
): number | null {
  const numerator = view.getUint32(offset, littleEndian);
  const denominator = view.getUint32(offset + 4, littleEndian);
  if (denominator === 0) return null;
  return numerator / denominator;
}

function readGpsCoordinate(
  view: DataView,
  entry: IfdEntry | undefined,
  ref: string | null,
  tiffStart: number,
  littleEndian: boolean,
): number | null {
  if (!entry || entry.type !== 5 || entry.count < 3) return null;
  const offset = entryDataOffset(entry, tiffStart);
  const degrees = readRational(view, offset, littleEndian);
  const minutes = readRational(view, offset + 8, littleEndian);
  const seconds = readRational(view, offset + 16, littleEndian);
  if (degrees == null || minutes == null || seconds == null) return null;
  const decimal = degrees + minutes / 60 + seconds / 3600;
  return ref?.toUpperCase() === "S" || ref?.toUpperCase() === "W" ? -decimal : decimal;
}

function readIfd(
  view: DataView,
  tiffStart: number,
  ifdOffset: number,
  littleEndian: boolean,
): Map<number, IfdEntry> {
  const entries = new Map<number, IfdEntry>();
  const start = tiffStart + ifdOffset;
  if (start < 0 || start + 2 > view.byteLength) return entries;
  const count = view.getUint16(start, littleEndian);
  for (let index = 0; index < count; index += 1) {
    const entryOffset = start + 2 + index * 12;
    if (entryOffset + 12 > view.byteLength) break;
    const tag = view.getUint16(entryOffset, littleEndian);
    const type = view.getUint16(entryOffset + 2, littleEndian);
    const valueCount = view.getUint32(entryOffset + 4, littleEndian);
    const valueOffset = view.getUint32(entryOffset + 8, littleEndian);
    if (!typeSize(type)) continue;
    entries.set(tag, {
      tag,
      type,
      count: valueCount,
      entryOffset,
      valueOffset,
    });
  }
  return entries;
}

export function parseExifTiff(
  bytes: Uint8Array,
  tiffStart = 0,
): PhotoExifMetadata | null {
  if (bytes.length < tiffStart + 8) return null;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const order = view.getUint16(tiffStart, false);
  if (order !== 0x4949 && order !== 0x4d4d) return null;
  const littleEndian = order === 0x4949;
  if (view.getUint16(tiffStart + 2, littleEndian) !== 42) return null;
  const ifdOffset = view.getUint32(tiffStart + 4, littleEndian);
  const ifd0 = readIfd(view, tiffStart, ifdOffset, littleEndian);
  if (ifd0.size === 0) return null;

  const orientationEntry = ifd0.get(TAG_ORIENTATION);
  const orientation = orientationEntry
    ? readUnsignedValue(view, orientationEntry, tiffStart, littleEndian)
    : null;

  const exifPointer = ifd0.get(TAG_EXIF_IFD);
  const exifIfdOffset = exifPointer
    ? readUnsignedValue(view, exifPointer, tiffStart, littleEndian)
    : null;
  const exifIfd =
    exifIfdOffset != null
      ? readIfd(view, tiffStart, exifIfdOffset, littleEndian)
      : new Map<number, IfdEntry>();

  const gpsPointer = ifd0.get(TAG_GPS_IFD);
  const gpsIfdOffset = gpsPointer
    ? readUnsignedValue(view, gpsPointer, tiffStart, littleEndian)
    : null;
  const gpsIfd =
    gpsIfdOffset != null
      ? readIfd(view, tiffStart, gpsIfdOffset, littleEndian)
      : new Map<number, IfdEntry>();

  const captureTime =
    readAsciiEntry(view, exifIfd.get(TAG_DATETIME_ORIGINAL), tiffStart) ??
    readAsciiEntry(view, exifIfd.get(TAG_DATETIME_DIGITIZED), tiffStart) ??
    readAsciiEntry(view, ifd0.get(TAG_DATETIME), tiffStart);

  const make = readAsciiEntry(view, ifd0.get(TAG_MAKE), tiffStart);
  const model = readAsciiEntry(view, ifd0.get(TAG_MODEL), tiffStart);
  const device = [make, model].filter(Boolean).join(" ") || null;

  const latRef = readAsciiEntry(view, gpsIfd.get(GPS_LAT_REF), tiffStart);
  const lonRef = readAsciiEntry(view, gpsIfd.get(GPS_LON_REF), tiffStart);
  const latitude = readGpsCoordinate(
    view,
    gpsIfd.get(GPS_LAT),
    latRef,
    tiffStart,
    littleEndian,
  );
  const longitude = readGpsCoordinate(
    view,
    gpsIfd.get(GPS_LON),
    lonRef,
    tiffStart,
    littleEndian,
  );
  const gps =
    latitude != null && longitude != null ? { latitude, longitude } : null;

  return { orientation, captureTime, gps, device };
}

export function parseExifFromJpeg(bytes: Uint8Array): PhotoExifMetadata | null {
  if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) return null;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let offset = 2;
  while (offset + 4 <= bytes.length) {
    if (bytes[offset] !== 0xff) return null;
    const marker = bytes[offset + 1];
    offset += 2;
    if (marker === 0xd8 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) {
      continue;
    }
    if (marker === 0xda) return null;
    const length = view.getUint16(offset, false);
    if (length < 2 || offset + length > bytes.length) return null;
    const payload = offset + 2;
    if (
      marker === 0xe1 &&
      payload + 6 <= bytes.length &&
      bytes[payload] === 0x45 &&
      bytes[payload + 1] === 0x78 &&
      bytes[payload + 2] === 0x69 &&
      bytes[payload + 3] === 0x66 &&
      bytes[payload + 4] === 0 &&
      bytes[payload + 5] === 0
    ) {
      return parseExifTiff(bytes, payload + 6);
    }
    offset += length;
  }
  return null;
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function toExifDateText(date: Date): string {
  return `${date.getFullYear()}:${pad2(date.getMonth() + 1)}:${pad2(date.getDate())} ${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`;
}

function decimalToDms(value: number): Array<[number, number]> {
  const absolute = Math.abs(value);
  let degrees = Math.floor(absolute);
  const minutesFloat = (absolute - degrees) * 60;
  let minutes = Math.floor(minutesFloat);
  let seconds = Math.round((minutesFloat - minutes) * 60 * 10000);
  if (seconds >= 600000) {
    seconds = 0;
    minutes += 1;
  }
  if (minutes >= 60) {
    minutes = 0;
    degrees += 1;
  }
  return [
    [degrees, 1],
    [minutes, 1],
    [seconds, 10000],
  ];
}

/**
 * Build a small EXIF APP1 block carrying only the metadata we actually have,
 * with orientation fixed to 1 because the canvas output is already upright.
 * This keeps backend capture_time/GPS fields for the processed JPEG.
 */
export function buildExifApp1Segment(
  info: PhotoWatermarkInfo,
  device?: string | null,
): Uint8Array | null {
  const hasTime = Boolean(info.capturedAt);
  const hasGps = Boolean(info.gps);
  const deviceText = (device ?? "").trim();
  const hasDevice = deviceText.length > 0;
  if (!hasTime && !hasGps) return null;

  const ifd0Count = 1 + (hasTime ? 2 : 0) + (hasGps ? 1 : 0) + (hasDevice ? 1 : 0);
  const ifd0Offset = 8;
  const ifd0Size = 2 + ifd0Count * 12 + 4;
  let cursor = ifd0Offset + ifd0Size;
  const dateOffset = hasTime ? cursor : 0;
  if (hasTime) cursor += 20;
  const exifIfdOffset = hasTime ? cursor : 0;
  if (hasTime) cursor += 2 + 12 + 4;
  const exifDateOffset = hasTime ? cursor : 0;
  if (hasTime) cursor += 20;
  const gpsIfdOffset = hasGps ? cursor : 0;
  if (hasGps) cursor += 2 + 4 * 12 + 4;
  const gpsLatOffset = hasGps ? cursor : 0;
  if (hasGps) cursor += 24;
  const gpsLonOffset = hasGps ? cursor : 0;
  if (hasGps) cursor += 24;
  const deviceOffset = hasDevice ? cursor : 0;
  if (hasDevice) cursor += deviceText.length + 1;

  const tiff = new Uint8Array(cursor);
  const view = new DataView(tiff.buffer);
  const u16 = (offset: number, value: number) =>
    view.setUint16(offset, value, true);
  const u32 = (offset: number, value: number) =>
    view.setUint32(offset, value, true);
  const writeAscii = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
    view.setUint8(offset + value.length, 0);
  };

  // TIFF header, little endian.
  view.setUint8(0, 0x49);
  view.setUint8(1, 0x49);
  u16(2, 42);
  u32(4, ifd0Offset);

  let offset = ifd0Offset;
  u16(offset, ifd0Count);
  offset += 2;
  const writeEntry = (tag: number, type: number, count: number, value: number) => {
    u16(offset, tag);
    u16(offset + 2, type);
    u32(offset + 4, count);
    u32(offset + 8, value);
    offset += 12;
  };
  writeEntry(TAG_ORIENTATION, 3, 1, 1);
  if (hasTime) {
    writeEntry(TAG_DATETIME, 2, 20, dateOffset);
    writeEntry(TAG_EXIF_IFD, 4, 1, exifIfdOffset);
  }
  if (hasGps) writeEntry(TAG_GPS_IFD, 4, 1, gpsIfdOffset);
  if (hasDevice) writeEntry(TAG_MODEL, 2, deviceText.length + 1, deviceOffset);
  u32(offset, 0);

  if (hasTime && info.capturedAt) {
    const dateText = toExifDateText(info.capturedAt);
    writeAscii(dateOffset, dateText);
    let exifOffset = exifIfdOffset;
    u16(exifOffset, 1);
    exifOffset += 2;
    u16(exifOffset, TAG_DATETIME_ORIGINAL);
    u16(exifOffset + 2, 2);
    u32(exifOffset + 4, 20);
    u32(exifOffset + 8, exifDateOffset);
    exifOffset += 12;
    u32(exifOffset, 0);
    writeAscii(exifDateOffset, dateText);
  }

  if (hasGps && info.gps) {
    const gps = info.gps;
    let gpsOffset = gpsIfdOffset;
    u16(gpsOffset, 4);
    gpsOffset += 2;
    const writeGpsEntry = (
      tag: number,
      type: number,
      count: number,
      value: number,
    ) => {
      u16(gpsOffset, tag);
      u16(gpsOffset + 2, type);
      u32(gpsOffset + 4, count);
      u32(gpsOffset + 8, value);
      gpsOffset += 12;
    };
    // Inline ASCII values live in the entry's 4-byte value field.
    writeGpsEntry(GPS_LAT_REF, 2, 2, 0);
    view.setUint8(gpsIfdOffset + 2 + 8, gps.latitude >= 0 ? 0x4e : 0x53);
    view.setUint8(gpsIfdOffset + 2 + 9, 0);
    writeGpsEntry(GPS_LAT, 5, 3, gpsLatOffset);
    writeGpsEntry(GPS_LON_REF, 2, 2, 0);
    // Longitude ref is the third entry: count(2) + 2 * 12 bytes.
    view.setUint8(gpsIfdOffset + 2 + 24 + 8, gps.longitude >= 0 ? 0x45 : 0x57);
    view.setUint8(gpsIfdOffset + 2 + 24 + 9, 0);
    writeGpsEntry(GPS_LON, 5, 3, gpsLonOffset);
    u32(gpsOffset, 0);

    const writeRationals = (
      dataOffset: number,
      values: Array<[number, number]>,
    ) => {
      values.forEach(([numerator, denominator], index) => {
        u32(dataOffset + index * 8, numerator);
        u32(dataOffset + index * 8 + 4, denominator);
      });
    };
    writeRationals(gpsLatOffset, decimalToDms(gps.latitude));
    writeRationals(gpsLonOffset, decimalToDms(gps.longitude));
  }

  if (hasDevice) writeAscii(deviceOffset, deviceText);

  const payloadLength = 6 + tiff.length;
  const segment = new Uint8Array(4 + payloadLength);
  segment[0] = 0xff;
  segment[1] = 0xe1;
  const segmentLength = payloadLength + 2;
  segment[2] = (segmentLength >> 8) & 0xff;
  segment[3] = segmentLength & 0xff;
  segment.set([0x45, 0x78, 0x69, 0x66, 0, 0], 4);
  segment.set(tiff, 10);
  return segment;
}

export function injectExifIntoJpeg(
  jpeg: Uint8Array,
  segment: Uint8Array,
): Uint8Array {
  if (jpeg.length < 2 || jpeg[0] !== 0xff || jpeg[1] !== 0xd8) return jpeg;
  const output = new Uint8Array(jpeg.length + segment.length);
  output.set(jpeg.subarray(0, 2), 0);
  output.set(segment, 2);
  output.set(jpeg.subarray(2), 2 + segment.length);
  return output;
}

async function preserveExifOnJpeg(
  blob: Blob,
  info: PhotoWatermarkInfo,
  device?: string | null,
): Promise<Blob> {
  const segment = buildExifApp1Segment(info, device);
  if (!segment) return blob;
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const output = injectExifIntoJpeg(bytes, segment);
  return new Blob([output.buffer as ArrayBuffer], {
    type: "image/jpeg",
  });
}


export async function readPhotoExif(file: File): Promise<PhotoExifMetadata | null> {
  const type = (file.type || "").toLowerCase();
  const extension = fileExtension(file.name);
  const isJpeg = type === "image/jpeg" || type === "image/jpg" || extension === "jpg" || extension === "jpeg";
  const isTiff = type === "image/tiff" || extension === "tif" || extension === "tiff";
  if (!isJpeg && !isTiff) return null;
  try {
    // EXIF lives near the start of the file; avoid loading a large photo twice.
    const buffer = await file.slice(0, 512 * 1024).arrayBuffer();
    const bytes = new Uint8Array(buffer);
    return isJpeg ? parseExifFromJpeg(bytes) : parseExifTiff(bytes);
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Canvas processing
// ---------------------------------------------------------------------------

type DecodedPhoto = {
  image: CanvasImageSource;
  width: number;
  height: number;
  close: () => void;
};

async function decodePhoto(file: File): Promise<DecodedPhoto> {
  if (typeof createImageBitmap === "function") {
    try {
      // "from-image" applies EXIF orientation, so the canvas is upright.
      const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
      if (bitmap.width > 0 && bitmap.height > 0) {
        return {
          image: bitmap,
          width: bitmap.width,
          height: bitmap.height,
          close: () => bitmap.close(),
        };
      }
      bitmap.close();
    } catch {
      // Fall through to the <img> decoder for browsers without a usable codec.
    }
  }

  if (typeof document === "undefined") {
    throw new PhotoProcessingError("Trình duyệt không đọc được ảnh này.");
  }
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.decoding = "async";
    image.src = url;
    if (typeof image.decode === "function") {
      await image.decode();
    } else {
      await new Promise<void>((resolve, reject) => {
        image.onload = () => resolve();
        image.onerror = () => reject(new Error("Image decode failed"));
      });
    }
    if (!image.naturalWidth || !image.naturalHeight) {
      throw new Error("Image has no pixels");
    }
    return {
      image,
      width: image.naturalWidth,
      height: image.naturalHeight,
      close: () => URL.revokeObjectURL(url),
    };
  } catch (error) {
    URL.revokeObjectURL(url);
    throw error;
  }
}

function wrapText(
  context: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length === 0) return [""];
  const lines: string[] = [];
  let current = words[0];
  for (const word of words.slice(1)) {
    const candidate = `${current} ${word}`;
    if (context.measureText(candidate).width <= maxWidth) {
      current = candidate;
    } else {
      lines.push(current);
      current = word;
    }
  }
  lines.push(current);
  return lines;
}

function drawWatermark(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  lines: string[],
): void {
  const fontSize = Math.min(44, Math.max(14, Math.round(width * 0.022)));
  const padding = Math.max(10, Math.round(fontSize * 0.65));
  const lineHeight = Math.round(fontSize * 1.35);
  context.font = `600 ${fontSize}px system-ui, -apple-system, "Segoe UI", sans-serif`;
  const contentWidth = Math.max(1, width - padding * 2);
  const wrapped = lines.flatMap((line) => wrapText(context, line, contentWidth));
  const barHeight = padding * 2 + wrapped.length * lineHeight;

  context.save();
  context.fillStyle = "rgba(0, 0, 0, 0.55)";
  context.fillRect(0, height - barHeight, width, barHeight);
  context.textBaseline = "top";
  context.fillStyle = "#ffffff";
  context.shadowColor = "rgba(0, 0, 0, 0.85)";
  context.shadowBlur = 3;
  wrapped.forEach((line, index) => {
    context.fillText(
      line,
      padding,
      height - barHeight + padding + index * lineHeight,
      contentWidth,
    );
  });
  context.restore();
}

function canvasToBlob(
  canvas: HTMLCanvasElement,
  quality: number,
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob);
        else reject(new PhotoProcessingError("Không nén được ảnh JPEG."));
      },
      "image/jpeg",
      quality,
    );
  });
}

async function encodeCanvasToTarget(canvas: HTMLCanvasElement): Promise<{
  blob: Blob;
  quality: number;
}> {
  let blob: Blob | null = null;
  let quality: number = JPEG_QUALITY_STEPS[0];
  for (const candidate of JPEG_QUALITY_STEPS) {
    quality = candidate;
    blob = await canvasToBlob(canvas, candidate);
    if (blob.size <= PHOTO_TARGET_BYTES) break;
  }
  if (!blob) throw new PhotoProcessingError("Không nén được ảnh JPEG.");
  return { blob, quality };
}

function outputJpegName(originalName: string): string {
  const base = (originalName || "photo").replace(/\.[^.]+$/, "").trim() || "photo";
  return `${base.slice(0, 120)}.jpg`;
}

export async function preparePhotoForUpload(
  file: File,
  options: PreparePhotoOptions,
): Promise<PreparedPhoto> {
  const support = photoFileSupport(file);
  if (!support.ok) throw new PhotoProcessingError(support.reason);

  const exif = await readPhotoExif(file);
  const info = resolvePhotoWatermarkInfo(exif, options);
  const decoded = await decodePhoto(file);
  try {
    const dimensions = fitPhotoDimensions(decoded.width, decoded.height);
    if (dimensions.width === 0 || dimensions.height === 0) {
      throw new PhotoProcessingError("Ảnh không có kích thước hợp lệ.");
    }
    const canvas = document.createElement("canvas");
    canvas.width = dimensions.width;
    canvas.height = dimensions.height;
    const context = canvas.getContext("2d");
    if (!context) throw new PhotoProcessingError("Trình duyệt không hỗ trợ Canvas.");
    // JPEG has no alpha; fill white so transparent PNG areas do not turn black.
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, dimensions.width, dimensions.height);
    context.drawImage(decoded.image, 0, 0, dimensions.width, dimensions.height);
    drawWatermark(context, dimensions.width, dimensions.height, photoWatermarkLines(info));

    const encoded = await encodeCanvasToTarget(canvas);
    let finalBlob = encoded.blob;
    try {
      finalBlob = await preserveExifOnJpeg(encoded.blob, info, exif?.device);
    } catch {
      // Metadata preservation is best-effort; the watermarked pixels stay.
    }
    const output = new File(
      [finalBlob],
      outputJpegName(file.name),
      { type: "image/jpeg", lastModified: file.lastModified || Date.now() },
    );
    return {
      file: output,
      width: dimensions.width,
      height: dimensions.height,
      bytes: output.size,
      quality: encoded.quality,
      overTarget: output.size > PHOTO_TARGET_BYTES,
      info,
    };
  } finally {
    decoded.close();
  }
}

export function getCurrentGpsPosition(
  timeoutMs = 8000,
): Promise<LocationFix | null> {
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    return Promise.resolve(null);
  }
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60000 },
    );
  });
}
