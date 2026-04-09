const STORAGE_KEY = "howl-server-url";
const HEALTH_INTERVAL_MS = 30_000;

export function getServerUrl(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

/**
 * Returns the effective API base URL.
 * Explicit stored URL (from QR Connect) takes precedence.
 * Falls back to current origin so that deployed instances
 * (app.howlvision.com) route through their own nginx proxy.
 */
export function getEffectiveServerUrl(): string | null {
  const stored = getServerUrl();
  if (stored) return stored;
  if (typeof window !== "undefined") return window.location.origin;
  return null;
}

export function setServerUrl(url: string): void {
  localStorage.setItem(STORAGE_KEY, url);
}

export function clearServerUrl(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export interface HealthStatus {
  reachable: boolean;
  /** True only when backend AND all upstreams (vision, ollama) are healthy. */
  fullPipeline: boolean;
}

export async function checkServerHealth(url: string): Promise<HealthStatus> {
  try {
    const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return { reachable: false, fullPipeline: false };
    const data = await res.json();
    const reachable = true;
    const fullPipeline = data.status === "ok";
    return { reachable, fullPipeline };
  } catch {
    return { reachable: false, fullPipeline: false };
  }
}

export type ConnectionState = "disconnected" | "degraded" | "connected";

/**
 * Starts polling server health. Returns cleanup function.
 * Calls onChange with the current connection state:
 *   - "connected"    — backend + all upstreams healthy
 *   - "degraded"     — backend reachable but vision-service or ollama down
 *   - "disconnected" — backend unreachable
 */
export function watchServerConnection(
  onChange: (state: ConnectionState) => void,
): () => void {
  let current: ConnectionState = "disconnected";
  let timer: ReturnType<typeof setInterval>;

  async function poll() {
    const url = getEffectiveServerUrl();
    if (!url) {
      if (current !== "disconnected") { current = "disconnected"; onChange(current); }
      return;
    }
    const health = await checkServerHealth(url);
    const next: ConnectionState = !health.reachable
      ? "disconnected"
      : health.fullPipeline
        ? "connected"
        : "degraded";
    if (next !== current) { current = next; onChange(next); }
  }

  poll();
  timer = setInterval(poll, HEALTH_INTERVAL_MS);
  return () => clearInterval(timer);
}
