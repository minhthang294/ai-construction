import { describe, expect, it } from "vitest";
import {
  buildExifApp1Segment,
  fitPhotoDimensions,
  formatPhotoBytes,
  injectExifIntoJpeg,
  JPEG_QUALITY_STEPS,
  parseExifDate,
  parseExifFromJpeg,
  parseExifTiff,
  PHOTO_MAX_LONG_EDGE,
  PHOTO_TARGET_BYTES,
  photoFileSupport,
  photoLocationSourceLabel,
  photoLocationValue,
  photoTimeSourceLabel,
  photoTimeValue,
  photoWatermarkLines,
  resolvePhotoWatermarkInfo,
} from "./photoProcessing";

function fakeFile(name: string, type: string, size = 100): File {
  return { name, type, size } as File;
}

function makeExifTiff(): Uint8Array {
  const bytes = new Uint8Array(256);
  const view = new DataView(bytes.buffer);
  const u16 = (offset: number, value: number) => view.setUint16(offset, value, true);
  const u32 = (offset: number, value: number) => view.setUint32(offset, value, true);
  const ascii = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
    view.setUint8(offset + value.length, 0);
  };

  // TIFF header (little endian), IFD0 at 8.
  view.setUint8(0, 0x49);
  view.setUint8(1, 0x49);
  u16(2, 42);
  u32(4, 8);

  const dateOffset = 62;
  const exifIfdOffset = 82;
  const exifDateOffset = 100;
  const gpsIfdOffset = 120;
  const latDataOffset = 174;
  const lonDataOffset = 198;

  let offset = 8;
  u16(offset, 4);
  offset += 2;
  // Orientation = 6 (rotated 90 degrees), kept as metadata only.
  u16(offset, 0x0112);
  u16(offset + 2, 3);
  u32(offset + 4, 1);
  u16(offset + 8, 6);
  offset += 12;
  // DateTime.
  u16(offset, 0x0132);
  u16(offset + 2, 2);
  u32(offset + 4, 20);
  u32(offset + 8, dateOffset);
  offset += 12;
  // Exif IFD pointer.
  u16(offset, 0x8769);
  u16(offset + 2, 4);
  u32(offset + 4, 1);
  u32(offset + 8, exifIfdOffset);
  offset += 12;
  // GPS IFD pointer.
  u16(offset, 0x8825);
  u16(offset + 2, 4);
  u32(offset + 4, 1);
  u32(offset + 8, gpsIfdOffset);
  offset += 12;
  u32(offset, 0);

  ascii(dateOffset, "2026:11:20 08:30:00");

  let exifOffset = exifIfdOffset;
  u16(exifOffset, 1);
  exifOffset += 2;
  u16(exifOffset, 0x9003);
  u16(exifOffset + 2, 2);
  u32(exifOffset + 4, 20);
  u32(exifOffset + 8, exifDateOffset);
  exifOffset += 12;
  u32(exifOffset, 0);
  ascii(exifDateOffset, "2026:11:20 09:15:00");

  let gpsOffset = gpsIfdOffset;
  u16(gpsOffset, 4);
  gpsOffset += 2;
  // Latitude ref (inline ASCII "N\0").
  u16(gpsOffset, 0x0001);
  u16(gpsOffset + 2, 2);
  u32(gpsOffset + 4, 2);
  view.setUint8(gpsOffset + 8, 0x4e);
  view.setUint8(gpsOffset + 9, 0);
  gpsOffset += 12;
  // Latitude (3 rationals).
  u16(gpsOffset, 0x0002);
  u16(gpsOffset + 2, 5);
  u32(gpsOffset + 4, 3);
  u32(gpsOffset + 8, latDataOffset);
  gpsOffset += 12;
  // Longitude ref.
  u16(gpsOffset, 0x0003);
  u16(gpsOffset + 2, 2);
  u32(gpsOffset + 4, 2);
  view.setUint8(gpsOffset + 8, 0x45);
  view.setUint8(gpsOffset + 9, 0);
  gpsOffset += 12;
  // Longitude (3 rationals).
  u16(gpsOffset, 0x0004);
  u16(gpsOffset + 2, 5);
  u32(gpsOffset + 4, 3);
  u32(gpsOffset + 8, lonDataOffset);
  gpsOffset += 12;
  u32(gpsOffset, 0);

  const writeRationals = (offset: number, values: Array<[number, number]>) => {
    values.forEach(([numerator, denominator], index) => {
      u32(offset + index * 8, numerator);
      u32(offset + index * 8 + 4, denominator);
    });
  };
  writeRationals(latDataOffset, [
    [10, 1],
    [30, 1],
    [0, 1],
  ]);
  writeRationals(lonDataOffset, [
    [106, 1],
    [45, 1],
    [0, 1],
  ]);
  return bytes;
}

function wrapExifInJpeg(tiff: Uint8Array): Uint8Array {
  const payload = new Uint8Array(6 + tiff.length);
  payload.set([0x45, 0x78, 0x69, 0x66, 0, 0], 0);
  payload.set(tiff, 6);
  const segmentLength = payload.length + 2;
  const jpeg = new Uint8Array(2 + 2 + 2 + payload.length);
  jpeg.set([0xff, 0xd8, 0xff, 0xe1], 0);
  jpeg[4] = (segmentLength >> 8) & 0xff;
  jpeg[5] = segmentLength & 0xff;
  jpeg.set(payload, 6);
  return jpeg;
}

describe("photo preparation metadata", () => {
  it("resizes only when the long edge exceeds 1920 px", () => {
    expect(fitPhotoDimensions(4000, 3000)).toEqual({ width: 1920, height: 1440 });
    expect(fitPhotoDimensions(1080, 1920)).toEqual({ width: 1080, height: 1920 });
    expect(fitPhotoDimensions(900, 600)).toEqual({ width: 900, height: 600 });
    expect(fitPhotoDimensions(0, 100)).toEqual({ width: 0, height: 0 });
    expect(fitPhotoDimensions(4000, 3000, PHOTO_MAX_LONG_EDGE)).toEqual({
      width: 1920,
      height: 1440,
    });
  });

  it("parses EXIF date/time and GPS from TIFF and JPEG APP1", () => {
    const tiff = makeExifTiff();
    const parsed = parseExifTiff(tiff);
    expect(parsed?.orientation).toBe(6);
    expect(parsed?.captureTime).toBe("2026:11:20 09:15:00");
    expect(parsed?.gps?.latitude).toBeCloseTo(10.5, 5);
    expect(parsed?.gps?.longitude).toBeCloseTo(106.75, 5);

    const fromJpeg = parseExifFromJpeg(wrapExifInJpeg(tiff));
    expect(fromJpeg?.captureTime).toBe("2026:11:20 09:15:00");
    expect(fromJpeg?.gps?.latitude).toBeCloseTo(10.5, 5);
  });

  it("uses EXIF and the user's location for a gallery photo", () => {
    const exif = {
      orientation: 1,
      captureTime: "2026:11:20 09:15:00",
      gps: { latitude: 10.5, longitude: 106.75 },
      device: null,
    };
    const info = resolvePhotoWatermarkInfo(exif, {
      source: "gallery",
      enteredLocation: "  Trụ T1  ",
    });
    expect(info.timeSource).toBe("exif");
    expect(info.gpsSource).toBe("exif");
    expect(info.locationText).toBe("Trụ T1");
    expect(photoTimeValue(info)).toBe("20/11/2026 09:15");
    expect(photoLocationValue(info)).toBe("Trụ T1 • 10.50000, 106.75000");
    expect(photoTimeSourceLabel(info)).toBe("EXIF");
    expect(photoLocationSourceLabel(info)).toBe("Vị trí nhập + GPS trong ảnh");
  });

  it("does not invent time or GPS for a gallery photo without EXIF", () => {
    const info = resolvePhotoWatermarkInfo(null, {
      source: "gallery",
      deviceGps: { latitude: 10.5, longitude: 106.75 },
    });
    expect(info.capturedAt).toBeNull();
    expect(info.timeSource).toBe("unknown");
    expect(info.gps).toBeNull();
    expect(photoTimeSourceLabel(info)).toBe("Chưa xác định");
    expect(photoLocationSourceLabel(info)).toBe("Chưa xác định");
    expect(photoWatermarkLines(info)).toEqual([
      "Thời gian: Chưa xác định",
      "Vị trí: Chưa xác định",
    ]);
  });

  it("uses device time and a new GPS fix for a camera capture", () => {
    const info = resolvePhotoWatermarkInfo(null, {
      source: "camera",
      capturedAt: new Date(2026, 10, 20, 8, 5, 0),
      deviceGps: { latitude: 10.1, longitude: 106.2 },
    });
    expect(info.timeSource).toBe("camera");
    expect(info.gpsSource).toBe("device");
    expect(photoTimeValue(info)).toBe("20/11/2026 08:05");
    expect(photoLocationValue(info)).toBe("10.10000, 106.20000");
  });

  it("preserves time/GPS in the processed JPEG with orientation 1", () => {
    const info = resolvePhotoWatermarkInfo(null, {
      source: "camera",
      capturedAt: new Date(2026, 10, 20, 8, 5, 0),
      deviceGps: { latitude: 10.5, longitude: 106.75 },
    });
    const segment = buildExifApp1Segment(info, "Test Phone");
    expect(segment).not.toBeNull();
    const jpeg = injectExifIntoJpeg(
      new Uint8Array([0xff, 0xd8, 0xff, 0xd9]),
      segment!,
    );
    const parsed = parseExifFromJpeg(jpeg);
    expect(parsed?.orientation).toBe(1);
    expect(parsed?.captureTime).toBe("2026:11:20 08:05:00");
    expect(parsed?.gps?.latitude).toBeCloseTo(10.5, 5);
    expect(parsed?.gps?.longitude).toBeCloseTo(106.75, 5);
    expect(parsed?.device).toBe("Test Phone");
  });

  it("does not write EXIF when the source has no metadata", () => {
    const info = resolvePhotoWatermarkInfo(null, { source: "gallery" });
    expect(buildExifApp1Segment(info)).toBeNull();
  });

  it("rejects invalid calendar dates", () => {
    expect(parseExifDate("2026:02:30 10:00:00")).toBeNull();
    expect(parseExifDate("not a date")).toBeNull();
  });

  it("reports unsupported formats clearly", () => {
    expect(photoFileSupport(fakeFile("a.jpg", "image/jpeg"))).toEqual({ ok: true });
    expect(photoFileSupport(fakeFile("a.HEIC", "image/heic"))).toEqual({ ok: true });
    expect(photoFileSupport(fakeFile("a.jpg", ""))).toEqual({ ok: true });
    expect(photoFileSupport(fakeFile("a.svg", "image/svg+xml")).ok).toBe(false);
    expect(photoFileSupport(fakeFile("notes.txt", "text/plain")).ok).toBe(false);
    expect(photoFileSupport(fakeFile("empty.jpg", "image/jpeg", 0)).ok).toBe(false);
  });

  it("uses the .82-.65 JPEG ladder with a 500 KB target", () => {
    expect(JPEG_QUALITY_STEPS[0]).toBe(0.82);
    expect(JPEG_QUALITY_STEPS.at(-1)).toBe(0.65);
    expect([...JPEG_QUALITY_STEPS].sort((a, b) => b - a)).toEqual([
      ...JPEG_QUALITY_STEPS,
    ]);
    expect(PHOTO_TARGET_BYTES).toBe(500 * 1024);
    expect(formatPhotoBytes(512 * 1024)).toBe("512 KB");
  });
});
