/**
 * EXIF orientation parsing + canvas transform for `compressImage`.
 *
 * Why this module exists: `createImageBitmap(file, { imageOrientation:
 * 'from-image' })` is not reliably honored across all browsers we ship to
 * (iOS Safari 15.x especially). Instead of relying on that option,
 * `image.ts` uses `imageOrientation: 'none'` (universal default) and
 * applies EXIF orientation itself via this module. That path is
 * deterministic on every browser that supports `createImageBitmap`,
 * including older WebViews and in-app browsers.
 */

/**
 * Reads the EXIF Orientation tag (0x0112) from the first 64 KB of a JPEG
 * file. Returns the tag value (1-8) or 1 if the file is not JPEG, has no
 * EXIF block, or the tag cannot be parsed. Never throws.
 *
 * Orientation semantics:
 *   1 — normal (no transform)
 *   2 — flip horizontal
 *   3 — rotate 180°
 *   4 — flip vertical
 *   5 — transpose (rotate 90° CCW + flip horizontal)
 *   6 — rotate 90° CW
 *   7 — transverse (rotate 90° CW + flip horizontal)
 *   8 — rotate 90° CCW
 */
export async function readExifOrientation(file: File | Blob): Promise<number> {
  try {
    const head = await file.slice(0, 64 * 1024).arrayBuffer();
    const view = new DataView(head);
    // JPEG SOI marker
    if (view.byteLength < 4 || view.getUint16(0) !== 0xffd8) return 1;

    let offset = 2;
    while (offset < view.byteLength - 4) {
      const marker = view.getUint16(offset);
      // APP1 (EXIF) marker
      if (marker === 0xffe1) {
        const exifStart = offset + 4;
        // "Exif\0\0" header
        if (view.getUint32(exifStart) !== 0x45786966) return 1;
        const tiff = exifStart + 6;
        // Byte order: II (little-endian) or MM (big-endian)
        const little = view.getUint16(tiff) === 0x4949;
        const ifd0 = tiff + view.getUint32(tiff + 4, little);
        if (ifd0 + 2 > view.byteLength) return 1;
        const entries = view.getUint16(ifd0, little);
        for (let i = 0; i < entries; i++) {
          const entry = ifd0 + 2 + i * 12;
          if (entry + 10 > view.byteLength) return 1;
          if (view.getUint16(entry, little) === 0x0112) {
            return view.getUint16(entry + 8, little);
          }
        }
        return 1;
      }
      // Stop at SOS (Start Of Scan) — no metadata after this point
      if (marker === 0xffda) return 1;
      // Non-APP1 marker — skip over its payload
      const segmentLength = view.getUint16(offset + 2);
      if (segmentLength < 2) return 1;
      offset += 2 + segmentLength;
    }
    return 1;
  } catch {
    return 1;
  }
}

/**
 * Applies the EXIF orientation as a canvas transform. Call this on a
 * context whose canvas has already been sized to the POST-rotation target
 * dimensions, passing the PRE-rotation (source) dimensions here. Then draw
 * the bitmap at (0, 0, sourceWidth, sourceHeight) and the transform will
 * map pixels correctly into the canvas.
 *
 * Expected caller pattern:
 *
 *   const swap = orientation >= 5 && orientation <= 8;
 *   const canvasW = swap ? sourceHeight : sourceWidth;
 *   const canvasH = swap ? sourceWidth  : sourceHeight;
 *   canvas.width  = canvasW;
 *   canvas.height = canvasH;
 *   applyExifOrientation(ctx, orientation, sourceWidth, sourceHeight);
 *   ctx.drawImage(bitmap, 0, 0, sourceWidth, sourceHeight);
 *
 * For orientation = 1, this is a no-op.
 */
export function applyExifOrientation(
  ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
  orientation: number,
  sourceWidth: number,
  sourceHeight: number,
): void {
  switch (orientation) {
    case 2:
      ctx.translate(sourceWidth, 0);
      ctx.scale(-1, 1);
      break;
    case 3:
      ctx.translate(sourceWidth, sourceHeight);
      ctx.rotate(Math.PI);
      break;
    case 4:
      ctx.translate(0, sourceHeight);
      ctx.scale(1, -1);
      break;
    case 5:
      ctx.rotate(0.5 * Math.PI);
      ctx.scale(1, -1);
      break;
    case 6:
      ctx.rotate(0.5 * Math.PI);
      ctx.translate(0, -sourceHeight);
      break;
    case 7:
      ctx.rotate(0.5 * Math.PI);
      ctx.translate(sourceWidth, -sourceHeight);
      ctx.scale(-1, 1);
      break;
    case 8:
      ctx.rotate(-0.5 * Math.PI);
      ctx.translate(-sourceWidth, 0);
      break;
    // case 1 (and any unknown value): no transform
  }
}
