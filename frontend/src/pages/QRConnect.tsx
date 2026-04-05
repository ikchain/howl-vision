import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import { QrCode, Wifi, WifiOff, ArrowLeft, X, Loader2 } from "lucide-react";
import jsQR from "jsqr";
import {
  getServerUrl,
  setServerUrl,
  clearServerUrl,
  checkServerHealth,
} from "../lib/connection";

type ScanState =
  | { phase: "scanning" }
  | { phase: "no-camera"; reason: string }
  | { phase: "validating"; url: string }
  | { phase: "connected"; url: string }
  | { phase: "error"; message: string };

function isHttpUrl(value: string): boolean {
  return value.startsWith("http://") || value.startsWith("https://");
}

export default function QRConnect() {
  const navigate = useNavigate();

  const existingUrl = getServerUrl();
  const [scanState, setScanState] = useState<ScanState>(
    existingUrl ? { phase: "connected", url: existingUrl } : { phase: "scanning" }
  );
  const [manualUrl, setManualUrl] = useState(existingUrl ?? "");
  const [cameraActive, setCameraActive] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // rafId is stored in a ref so the cleanup closure always sees the latest value
  const rafIdRef = useRef<number>(0);
  // Guard: prevents the scan loop from processing after unmount
  const mountedRef = useRef(true);

  // Stop camera stream and cancel pending animation frame
  const stopCamera = useCallback(() => {
    cancelAnimationFrame(rafIdRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
  }, []);

  // Connect: validate URL, persist, navigate
  const connect = useCallback(
    async (url: string) => {
      const trimmed = url.trim();
      if (!isHttpUrl(trimmed)) {
        setScanState({ phase: "error", message: "URL must start with http:// or https://" });
        return;
      }
      setScanState({ phase: "validating", url: trimmed });
      stopCamera();

      const ok = await checkServerHealth(trimmed);
      if (!mountedRef.current) return;

      if (ok) {
        setServerUrl(trimmed);
        setScanState({ phase: "connected", url: trimmed });
        // Small delay so the user sees the connected state before leaving
        setTimeout(() => {
          if (mountedRef.current) navigate("/capture");
        }, 800);
      } else {
        setScanState({
          phase: "error",
          message: "Could not reach the server at that URL. Check it's running and reachable.",
        });
      }
    },
    [navigate, stopCamera]
  );

  // Scan loop: reads a frame from the video into the canvas, then runs jsQR
  const scheduleScan = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !mountedRef.current) return;

    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;

    function tick() {
      if (!mountedRef.current || !video || !canvas || !ctx) return;
      // Only scan when the video has actual pixel data
      if (video!.readyState === video!.HAVE_ENOUGH_DATA) {
        canvas!.width = video!.videoWidth;
        canvas!.height = video!.videoHeight;
        ctx.drawImage(video!, 0, 0, canvas!.width, canvas!.height);
        const imageData = ctx.getImageData(0, 0, canvas!.width, canvas!.height);
        const code = jsQR(imageData.data, imageData.width, imageData.height, {
          inversionAttempts: "dontInvert",
        });
        if (code && isHttpUrl(code.data)) {
          // Found a valid-looking URL — try to connect
          connect(code.data);
          return; // stop the loop; connect() calls stopCamera
        }
      }
      rafIdRef.current = requestAnimationFrame(tick);
    }

    rafIdRef.current = requestAnimationFrame(tick);
  }, [connect]);

  // Start camera
  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          // Rear camera preferred on mobile
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      });
      if (!mountedRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch(() => {
          // play() can be interrupted if the component unmounts immediately
        });
      }
      setCameraActive(true);
      setScanState({ phase: "scanning" });
      scheduleScan();
    } catch (err) {
      const reason =
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Camera permission denied. Use the manual URL input below."
          : "Camera not available. Use the manual URL input below.";
      setScanState({ phase: "no-camera", reason });
    }
  }, [scheduleScan]);

  // Auto-start camera when mounting in scanning state (not already connected)
  useEffect(() => {
    mountedRef.current = true;
    if (!existingUrl) {
      startCamera();
    }
    return () => {
      mountedRef.current = false;
      stopCamera();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // ^ Intentionally run once on mount. startCamera/stopCamera are stable callbacks.

  function handleDisconnect() {
    clearServerUrl();
    setManualUrl("");
    setScanState({ phase: "scanning" });
    startCamera();
  }

  function handleManualConnect() {
    connect(manualUrl);
  }

  function handleRetry() {
    setScanState({ phase: "scanning" });
    startCamera();
  }

  const isValidating = scanState.phase === "validating";
  const isConnected = scanState.phase === "connected";

  return (
    <div className="py-6 px-4 space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          to="/capture"
          className="text-content-muted hover:text-content-primary transition-colors"
          aria-label="Back to capture"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-lg font-semibold text-content-primary">Connect to Clinic Hub</h1>
          <p className="text-xs text-content-muted">
            Scan the QR on the hub or enter the URL manually
          </p>
        </div>
      </div>

      {/* Camera viewfinder */}
      {!isConnected && (
        <div className="relative rounded-xl overflow-hidden bg-ocean-deep border border-ocean-border aspect-square max-h-72 flex items-center justify-center">
          {/* Live video feed */}
          <video
            ref={videoRef}
            className={`absolute inset-0 w-full h-full object-cover ${cameraActive ? "opacity-100" : "opacity-0"}`}
            muted
            playsInline
            aria-hidden="true"
          />

          {/* Hidden canvas for pixel extraction only */}
          <canvas ref={canvasRef} className="hidden" aria-hidden="true" />

          {/* Scanning overlay — only shown when camera is active */}
          {cameraActive && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              {/* Corner brackets */}
              <div className="relative w-48 h-48">
                <span className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-teal rounded-tl-sm" />
                <span className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-teal rounded-tr-sm" />
                <span className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-teal rounded-bl-sm" />
                <span className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-teal rounded-br-sm" />
                {/* Animated scan line */}
                <span
                  className="absolute left-2 right-2 h-px bg-teal/70 animate-scan-line"
                  style={{
                    // CSS animation defined inline because the project has no keyframes token
                    animation: "scanLine 2s ease-in-out infinite",
                    top: "50%",
                  }}
                />
              </div>
            </div>
          )}

          {/* Idle placeholder when camera hasn't started or was denied */}
          {!cameraActive && scanState.phase !== "no-camera" && (
            <div className="flex flex-col items-center gap-3 text-content-muted">
              <QrCode className="w-12 h-12 opacity-40" />
              <span className="text-xs">Starting camera…</span>
            </div>
          )}

          {/* No camera fallback */}
          {scanState.phase === "no-camera" && (
            <div className="flex flex-col items-center gap-2 px-6 text-center">
              <WifiOff className="w-8 h-8 text-content-secondary opacity-60" />
              <p className="text-xs text-content-muted">{scanState.reason}</p>
            </div>
          )}

          {/* Validating overlay */}
          {isValidating && (
            <div className="absolute inset-0 bg-ocean-deep/80 flex flex-col items-center justify-center gap-2">
              <Loader2 className="w-8 h-8 text-teal-text animate-spin" />
              <p className="text-xs text-content-secondary">Checking server…</p>
            </div>
          )}
        </div>
      )}

      {/* Inline keyframe: avoids a global CSS file just for this one animation */}
      <style>{`
        @keyframes scanLine {
          0%, 100% { transform: translateY(-60px); opacity: 0.4; }
          50%       { transform: translateY(60px);  opacity: 1;   }
        }
      `}</style>

      {/* Status text below viewfinder */}
      {!isConnected && (
        <p className="text-center text-xs text-content-muted" aria-live="polite">
          {scanState.phase === "scanning" && cameraActive && "Point camera at the hub QR code"}
          {scanState.phase === "scanning" && !cameraActive && "Waiting for camera…"}
          {scanState.phase === "no-camera" && "Camera unavailable — use manual input"}
          {scanState.phase === "validating" && `Connecting to ${scanState.url}…`}
          {scanState.phase === "error" && (
            <span className="text-red-400">{scanState.message}</span>
          )}
        </p>
      )}

      {/* Retry link after error */}
      {scanState.phase === "error" && (
        <div className="text-center">
          <button
            onClick={handleRetry}
            className="text-xs text-teal-text hover:text-teal-light transition-colors"
          >
            Try scanning again
          </button>
        </div>
      )}

      {/* Connected state */}
      {isConnected && (
        <div className="bg-ocean-surface border border-teal/30 rounded-xl p-4 flex items-start gap-3">
          <div className="w-8 h-8 rounded-full bg-teal/15 flex items-center justify-center flex-shrink-0 mt-0.5">
            <Wifi className="w-4 h-4 text-teal-text" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-content-primary">Connected</p>
            <p className="text-xs text-content-muted truncate mt-0.5">{scanState.url}</p>
          </div>
          <button
            onClick={handleDisconnect}
            className="flex items-center gap-1 text-xs text-content-muted hover:text-red-400 transition-colors flex-shrink-0"
            aria-label="Disconnect from clinic hub"
          >
            <X className="w-3.5 h-3.5" />
            Disconnect
          </button>
        </div>
      )}

      {/* Divider */}
      {!isConnected && (
        <div className="flex items-center gap-3" role="separator" aria-hidden="true">
          <div className="flex-1 h-px bg-ocean-border" />
          <span className="text-xs text-content-muted whitespace-nowrap">or enter URL manually</span>
          <div className="flex-1 h-px bg-ocean-border" />
        </div>
      )}

      {/* Manual URL input */}
      {!isConnected && (
        <div className="space-y-2">
          <label htmlFor="server-url" className="sr-only">
            Clinic Hub server URL
          </label>
          <input
            id="server-url"
            type="url"
            value={manualUrl}
            onChange={(e) => setManualUrl(e.target.value)}
            placeholder="http://192.168.1.x:20001"
            className="w-full bg-ocean-surface border border-ocean-border focus:border-teal focus:outline-none rounded-lg px-3 py-2.5 text-sm text-content-primary placeholder:text-content-muted transition-colors"
            inputMode="url"
            autoComplete="url"
            onKeyDown={(e) => {
              if (e.key === "Enter" && manualUrl.trim()) handleManualConnect();
            }}
          />
          <button
            onClick={handleManualConnect}
            disabled={isValidating || !manualUrl.trim()}
            className="w-full flex items-center justify-center gap-2 bg-teal hover:bg-teal-hover disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl px-4 py-2.5 text-sm font-medium transition-colors"
          >
            {isValidating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Connecting…
              </>
            ) : (
              <>
                <Wifi className="w-4 h-4" />
                Connect
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
