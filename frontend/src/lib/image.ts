/**
 * Client-side image compression for /api/v1/analyze and /api/v1/chat uploads.
 *
 * Eliminates the 5 MB upload wall by resizing + re-encoding photos in the
 * browser before they hit the network. Uses vanilla Canvas APIs
 * (`createImageBitmap`, `OffscreenCanvas`, `HTMLCanvasElement`) — zero npm
 * dependencies.
 *
 * EXIF orientation is applied manually (see `exif.ts`) rather than relying
 * on `createImageBitmap({ imageOrientation: 'from-image' })`, whose support
 * on iOS Safari 15.x is not reliably verifiable. We pass `'none'` (the
 * universal default per the HTML spec) and rotate/flip the canvas context
 * ourselves based on the EXIF tag. Works on every browser that supports
 * `createImageBitmap`, including older WebViews.
 *
 * Fail-open on every expected failure path (unsupported type, decode error,
 * encode error, output not smaller than input): the original unchanged file
 * is returned so the upload can still attempt through the 18 MB hard cap.
 * Programmer errors (invalid options) throw.
 */

import { readExifOrientation, applyExifOrientation } from "./exif";

export interface CompressOptions {
  /** Max long dimension in pixels. Must be >= 1. Default 2048. */
  maxDim?: number;
  /** JPEG quality. Must be in (0, 1]. Default 0.85. */
  quality?: number;
  /** File size below which input is returned unchanged. Must be >= 0. Default 500 KB. */
  skipBelowBytes?: number;
}

export type SkipReason =
  | "below-threshold"
  | "unsupported-type"
  | "decode-failed"
  | "encode-failed"
  | "output-larger";

export type CompressResult =
  | {
      file: File;
      beforeBytes: number;
      afterBytes: number;
      skipped: false;
    }
  | {
      file: File;
      beforeBytes: number;
      afterBytes: number;
      skipped: true;
      reason: SkipReason;
    };

const DEFAULT_MAX_DIM = 2048;
// Quality locked at 0.95 post-AC-10 eval. See spec §3 D3 and §14 for the
// empirical rationale: Q=0.95 has the most conservative margin on every
// direction-sensitive metric (p95 |Δsoftmax|, MCE delta) while the UX cost
// vs 0.85 is imperceptible in practice (300 ms upload delta on 4G,
// indistinguishable at 360 px display width).
const DEFAULT_QUALITY = 0.95;
const DEFAULT_SKIP_BELOW_BYTES = 500 * 1024;

const SUPPORTED_MIME: ReadonlySet<string> = new Set([
  "image/jpeg",
  "image/jpg",
  "image/png",
  "image/webp",
  "image/heic",
  "image/heif",
]);

/**
 * Feature-detect the modern OffscreenCanvas encoding path. Safari <16.4 and
 * some older Android WebViews don't expose `convertToBlob`; those land on
 * the HTMLCanvasElement.toBlob fallback.
 */
function supportsOffscreenCanvasBlob(): boolean {
  return (
    typeof OffscreenCanvas !== "undefined" &&
    typeof OffscreenCanvas.prototype.convertToBlob === "function"
  );
}

function rename(file: File): string {
  return file.name.replace(/\.(heic|heif|png|webp|jpeg|jpg)$/i, "") + ".jpg";
}

/**
 * Compresses and resizes `file` before upload.
 *
 * Throws only for programmer errors (out-of-range options). For any other
 * failure — unsupported type, corrupt input, missing browser API — the
 * original file is returned with `skipped: true` and a reason.
 */
export async function compressImage(
  file: File,
  opts?: CompressOptions,
): Promise<CompressResult> {
  const maxDim = opts?.maxDim ?? DEFAULT_MAX_DIM;
  const quality = opts?.quality ?? DEFAULT_QUALITY;
  const skipBelowBytes = opts?.skipBelowBytes ?? DEFAULT_SKIP_BELOW_BYTES;

  // Programmer errors throw — distinguish from user-input failures.
  if (maxDim < 1) {
    throw new Error(`compressImage: maxDim must be >= 1, got ${maxDim}`);
  }
  if (quality <= 0 || quality > 1) {
    throw new Error(`compressImage: quality must be in (0, 1], got ${quality}`);
  }
  if (skipBelowBytes < 0) {
    throw new Error(
      `compressImage: skipBelowBytes must be >= 0, got ${skipBelowBytes}`,
    );
  }

  // Guard 1: below threshold — no benefit to recompressing, potential
  // generational loss. Return unchanged.
  if (file.size <= skipBelowBytes) {
    return {
      file,
      beforeBytes: file.size,
      afterBytes: file.size,
      skipped: true,
      reason: "below-threshold",
    };
  }

  // Guard 2: MIME type outside the allow-list. Don't try to decode unknown
  // formats — let them flow to the server's 18 MB cap guard.
  if (!SUPPORTED_MIME.has(file.type)) {
    return {
      file,
      beforeBytes: file.size,
      afterBytes: file.size,
      skipped: true,
      reason: "unsupported-type",
    };
  }

  // Decode off main thread with explicit `imageOrientation: 'none'` so the
  // raw pixel data is returned WITHOUT any browser-applied EXIF rotation.
  // We apply orientation ourselves below via `applyExifOrientation`. This
  // removes the iOS Safari 15 ambiguity on `'from-image'` support.
  let bitmap: ImageBitmap;
  let orientation = 1;
  try {
    // Parse EXIF in parallel with decode — the file is already in memory
    // and the parse reads only the first 64 KB, so this is near-free.
    const [decoded, exif] = await Promise.all([
      createImageBitmap(file, { imageOrientation: "none" }),
      readExifOrientation(file),
    ]);
    bitmap = decoded;
    orientation = exif;
  } catch (e) {
    console.debug("[compressImage] decode failed:", e);
    return {
      file,
      beforeBytes: file.size,
      afterBytes: file.size,
      skipped: true,
      reason: "decode-failed",
    };
  }

  let blob: Blob;
  try {
    // Compute scaled dimensions in the POST-rotation (display) coordinate
    // space. Orientation 5-8 swap width↔height semantically; the canvas
    // must match that swap.
    const swap = orientation >= 5 && orientation <= 8;
    const sourceW = bitmap.width;
    const sourceH = bitmap.height;
    const logicalW = swap ? sourceH : sourceW;
    const logicalH = swap ? sourceW : sourceH;
    const longDim = Math.max(logicalW, logicalH);
    const scale = longDim <= maxDim ? 1 : maxDim / longDim;

    // Canvas size = post-rotation, scaled output.
    const targetW = Math.max(1, Math.round(logicalW * scale));
    const targetH = Math.max(1, Math.round(logicalH * scale));

    // drawImage uses pre-rotation (source) dims at the same scale; the
    // applyExifOrientation transform maps them into the canvas.
    const drawW = Math.max(1, Math.round(sourceW * scale));
    const drawH = Math.max(1, Math.round(sourceH * scale));

    if (supportsOffscreenCanvasBlob()) {
      const canvas = new OffscreenCanvas(targetW, targetH);
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        throw new Error("2d context unavailable (OffscreenCanvas)");
      }
      applyExifOrientation(ctx, orientation, drawW, drawH);
      ctx.drawImage(bitmap, 0, 0, drawW, drawH);
      blob = await canvas.convertToBlob({ type: "image/jpeg", quality });
    } else {
      const canvas = document.createElement("canvas");
      canvas.width = targetW;
      canvas.height = targetH;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        throw new Error("2d context unavailable (HTMLCanvasElement)");
      }
      applyExifOrientation(ctx, orientation, drawW, drawH);
      ctx.drawImage(bitmap, 0, 0, drawW, drawH);
      blob = await new Promise<Blob>((resolve, reject) =>
        canvas.toBlob(
          (b) => (b ? resolve(b) : reject(new Error("toBlob returned null"))),
          "image/jpeg",
          quality,
        ),
      );
    }

    // Safari 16.4-16.5 has a known bug where convertToBlob occasionally
    // resolves with a zero-byte Blob. Treat that as encode failure.
    if (!blob || blob.size === 0) {
      throw new Error("encode produced empty blob");
    }
  } catch (e) {
    console.debug("[compressImage] encode failed:", e);
    return {
      file,
      beforeBytes: file.size,
      afterBytes: file.size,
      skipped: true,
      reason: "encode-failed",
    };
  } finally {
    // Always release GPU/memory held by the ImageBitmap, regardless of
    // success, encode failure, or the `output-larger` return below.
    bitmap.close();
  }

  // Guard 3: output must actually be smaller. JPEG re-encoding a photo that
  // was already maximally compressed can produce a larger file; in that
  // case, pass the original through unchanged.
  if (blob.size >= file.size) {
    return {
      file,
      beforeBytes: file.size,
      afterBytes: file.size,
      skipped: true,
      reason: "output-larger",
    };
  }

  const outFile = new File([blob], rename(file), {
    type: "image/jpeg",
    lastModified: file.lastModified,
  });

  return {
    file: outFile,
    beforeBytes: file.size,
    afterBytes: blob.size,
    skipped: false,
  };
}
