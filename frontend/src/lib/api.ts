import type { CasesSearchResponse } from "../types";

const API_BASE = "/api/v1";

export async function searchCases(
  q: string,
  limit = 10,
): Promise<CasesSearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  const res = await fetch(`${API_BASE}/cases/search?${params}`);
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/**
 * Hard cap on image upload size — conservative safety net, not the primary
 * UX wall. After `compressImage` runs (frontend/src/lib/image.ts), real
 * photos should be <2 MB. This cap exists only for the fail-open path where
 * compression skipped due to an unexpected error (corrupt file, decode
 * failure, unsupported MIME type).
 *
 * Applies to both transport paths:
 *   - /api/v1/analyze (multipart/form-data): nginx accepts up to 25 MB.
 *     18 MB here leaves 7 MB headroom.
 *   - /api/v1/chat    (base64-in-JSON):       nginx 25 MB ÷ 1.333 base64
 *     overhead ≈ 18.75 MB binary ceiling. Rounded down to 18 MB.
 *
 * Single constant by design (see spec §3 D4). If the transports diverge
 * enough to need different caps in the future, split then — not now.
 */
export const MAX_IMAGE_SIZE_BYTES = 18 * 1024 * 1024;
