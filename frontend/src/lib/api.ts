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

/** Max image size: 5MB (base64 adds ~33% overhead) */
export const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;
