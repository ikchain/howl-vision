import { useRegisterSW } from "virtual:pwa-register/react";

export function UpdateBanner() {
  const { needRefresh: [needRefresh, setNeedRefresh], updateServiceWorker } = useRegisterSW({
    onRegisterError(error: unknown) {
      console.warn("SW registration error:", error);
    },
  });

  if (!needRefresh) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="bg-yellow-600/95 text-black px-4 py-2 flex items-center justify-between gap-3 text-xs sm:text-sm border-b border-yellow-700/40"
    >
      <span className="flex-1 min-w-0">
        New version available. Reload to apply.
      </span>
      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          type="button"
          onClick={() => updateServiceWorker(true)}
          className="px-2.5 py-1 rounded bg-black text-yellow-300 font-semibold hover:bg-black/80 transition-colors"
        >
          Reload
        </button>
        <button
          type="button"
          onClick={() => setNeedRefresh(false)}
          aria-label="Dismiss update notice"
          className="px-2 py-1 rounded text-black/70 hover:text-black"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
