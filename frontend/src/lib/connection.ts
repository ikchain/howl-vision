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

export async function checkServerHealth(url: string): Promise<boolean> {
  try {
    const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === "ok";
  } catch {
    return false;
  }
}

/**
 * Starts polling server health. Returns cleanup function.
 * Calls onChange(true) when server becomes available, onChange(false) when lost.
 */
export function watchServerConnection(
  onChange: (connected: boolean) => void,
): () => void {
  let alive = false;
  let timer: ReturnType<typeof setInterval>;

  async function poll() {
    const url = getServerUrl();
    if (!url) {
      if (alive) { alive = false; onChange(false); }
      return;
    }
    const ok = await checkServerHealth(url);
    if (ok !== alive) { alive = ok; onChange(ok); }
  }

  poll();
  timer = setInterval(poll, HEALTH_INTERVAL_MS);
  return () => clearInterval(timer);
}
