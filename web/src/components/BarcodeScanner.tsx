"use client";

import { useCallback, useEffect, useRef, useState } from "react";

declare class BarcodeDetector {
  constructor(options?: { formats: string[] });
  detect(image: CanvasImageSource): Promise<Array<{ rawValue: string }>>;
}

interface BarcodeScannerProps {
  onDetected: (barcode: string) => void;
}

type ScanPhase = "idle" | "scanning";

interface ZBarSymbol {
  decode(): string;
  typeName: string;
}

type ScanImageDataFn = (data: ImageData) => Promise<ZBarSymbol[]>;

const DECODE_INTERVAL_MS = 300;
// Guide region: centre 70 % wide × 35 % tall
const GUIDE = { xRatio: 0.15, yRatio: 0.325, wRatio: 0.7, hRatio: 0.35 };

// Retail product codes only — ZBar also decodes QR, Code-39, etc., which must
// never reach product lookup
const ZBAR_RETAIL_TYPES = new Set(["ZBAR_EAN13", "ZBAR_UPCA", "ZBAR_EAN8"]);

function isValidGs1Checksum(code: string): boolean {
  const digits = code.split("").map(Number);
  const check = digits.pop()!;
  // GS1 mod-10: weights 3,1,3,… from the digit adjacent to the check digit
  let sum = 0;
  digits.reverse().forEach((d, i) => {
    sum += d * (i % 2 === 0 ? 3 : 1);
  });
  return (10 - (sum % 10)) % 10 === check;
}

/**
 * Validate a raw read and normalize it to the form product lookup expects.
 * UPC-A (12 digits) is an EAN-13 with a leading zero. Returns null for
 * anything that is not a checksum-valid retail code.
 */
function normalizeRetailCode(raw: string): string | null {
  const trimmed = raw.trim();
  let code: string;
  if (/^\d{12}$/.test(trimmed)) {
    code = `0${trimmed}`;
  } else if (/^\d{13}$/.test(trimmed) || /^\d{8}$/.test(trimmed)) {
    code = trimmed;
  } else {
    return null;
  }
  return isValidGs1Checksum(code) ? code : null;
}

export default function BarcodeScanner({ onDetected }: BarcodeScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onDetectedRef = useRef(onDetected);
  const activeRef = useRef(true);
  const firedRef = useRef(false);
  const decodingRef = useRef(false);
  const tickRef = useRef(0);
  const scanImageDataRef = useRef<ScanImageDataFn | null>(null);
  const barcodeDetectorRef = useRef<BarcodeDetector | null>(null);

  const [phase, setPhase] = useState<ScanPhase>("idle");
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [torchOn, setTorchOn] = useState(false);
  const [torchSupported, setTorchSupported] = useState(false);

  useEffect(() => {
    onDetectedRef.current = onDetected;
  });

  // Preload ZBar WASM and set up BarcodeDetector once
  useEffect(() => {
    if ("BarcodeDetector" in window) {
      barcodeDetectorRef.current = new BarcodeDetector({
        formats: ["ean_13", "ean_8", "upc_a"],
      });
    }
    import("@undecaf/zbar-wasm")
      .then((m) => {
        scanImageDataRef.current = m.scanImageData as ScanImageDataFn;
      })
      .catch(() => {
        // Without WASM and without a native detector nothing can decode —
        // surface that instead of scanning forever
        if (!barcodeDetectorRef.current) {
          setCameraError("Barcode reader failed to load. Please enter the barcode manually.");
        }
      });
  }, []);

  const fireDetected = useCallback((code: string): void => {
    if (firedRef.current || !activeRef.current) return;
    firedRef.current = true;
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    onDetectedRef.current(code);
  }, []);

  const decodeTick = useCallback(async () => {
    // Skip ticks while a previous decode is still running — WASM decodes can
    // exceed the interval on slow devices and must not overlap
    if (decodingRef.current || firedRef.current || !activeRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.videoWidth === 0) return;

    decodingRef.current = true;
    try {
      // 1. Native BarcodeDetector — fast, OS-level, handles curved surfaces well
      if (barcodeDetectorRef.current) {
        try {
          const results = await barcodeDetectorRef.current.detect(video);
          for (const result of results) {
            const code = normalizeRetailCode(result.rawValue);
            if (code) {
              fireDetected(code);
              return;
            }
          }
        } catch {
          /* fall through to ZBar */
        }
      }

      // 2. ZBar WASM — alternate between the guide-region crop (less noise)
      // and the full frame (catches barcodes held outside the guide)
      const scanImageData = scanImageDataRef.current;
      if (!scanImageData) return;

      tickRef.current += 1;
      const fullFrame = tickRef.current % 2 === 0;
      const sx = fullFrame ? 0 : Math.round(video.videoWidth * GUIDE.xRatio);
      const sy = fullFrame ? 0 : Math.round(video.videoHeight * GUIDE.yRatio);
      const sw = fullFrame ? video.videoWidth : Math.round(video.videoWidth * GUIDE.wRatio);
      const sh = fullFrame ? video.videoHeight : Math.round(video.videoHeight * GUIDE.hRatio);

      canvas.width = sw;
      canvas.height = sh;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) return;
      ctx.drawImage(video, sx, sy, sw, sh, 0, 0, sw, sh);
      const imageData = ctx.getImageData(0, 0, sw, sh);

      const symbols = await scanImageData(imageData);
      for (const symbol of symbols) {
        if (!ZBAR_RETAIL_TYPES.has(symbol.typeName)) continue;
        const code = normalizeRetailCode(symbol.decode());
        if (code) {
          fireDetected(code);
          return;
        }
      }
    } finally {
      decodingRef.current = false;
    }
  }, [fireDetected]);

  const startDecodeLoop = useCallback(() => {
    if (intervalRef.current !== null || firedRef.current) return;
    setPhase("scanning");
    intervalRef.current = setInterval(() => {
      void decodeTick();
    }, DECODE_INTERVAL_MS);
  }, [decodeTick]);

  // Camera setup and cleanup
  useEffect(() => {
    activeRef.current = true;

    navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } },
      })
      .then((stream) => {
        if (!activeRef.current) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;

        const track = stream.getVideoTracks()[0];
        const caps = track?.getCapabilities?.() as Record<string, unknown> | undefined;
        if (caps?.torch) setTorchSupported(true);
        // Sharp lines are essential for EAN decoding — request continuous
        // autofocus where the device supports it
        if (Array.isArray(caps?.focusModes) && caps.focusModes.includes("continuous")) {
          track
            .applyConstraints({
              advanced: [{ focusMode: "continuous" } as unknown as MediaTrackConstraintSet],
            })
            .catch(() => {});
        }

        const video = videoRef.current;
        if (video) {
          video.srcObject = stream;
          // iOS Safari does not always honour autoplay; the rejection (e.g.
          // backgrounded tab) is non-fatal
          video.play().catch(() => {});
          // canplay may already have fired before React attached the listener
          if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
            startDecodeLoop();
          }
        }
      })
      .catch((err: unknown) => {
        if (!activeRef.current) return;
        if (err instanceof DOMException && err.name === "NotAllowedError") {
          setCameraError("Camera permission denied. Please allow camera access and try again.");
        } else {
          setCameraError("Failed to start camera.");
        }
      });

    return () => {
      activeRef.current = false;
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [startDecodeLoop]);

  const handleTorchToggle = useCallback(async () => {
    const track = streamRef.current?.getVideoTracks()[0];
    if (!track) return;
    const next = !torchOn;
    await track.applyConstraints({
      advanced: [{ torch: next } as unknown as MediaTrackConstraintSet],
    });
    setTorchOn(next);
  }, [torchOn]);

  if (cameraError) {
    return (
      <div role="alert" className="rounded-lg bg-destructive/10 p-4 text-destructive">
        <p>{cameraError}</p>
      </div>
    );
  }

  return (
    <div className="relative space-y-3">
      <div className="relative overflow-hidden rounded-lg bg-black">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          aria-label="Camera viewfinder"
          className="w-full"
          onCanPlay={startDecodeLoop}
        />
        {phase === "scanning" && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 flex items-center justify-center"
          >
            {/* Box-shadow creates dark overlay outside the guide rectangle */}
            <div
              className="h-[35%] w-[70%] rounded border-2 border-white/90"
              style={{ boxShadow: "0 0 0 9999px rgba(0,0,0,0.45)" }}
            />
          </div>
        )}
      </div>

      <canvas ref={canvasRef} className="hidden" aria-hidden="true" />

      {phase === "idle" && (
        <p className="text-center text-xs text-muted-foreground">Starting camera…</p>
      )}
      {phase === "scanning" && (
        <p className="text-center text-xs text-muted-foreground">Align barcode with the frame</p>
      )}

      {torchSupported && (
        <button
          aria-label={torchOn ? "Turn off flashlight" : "Turn on flashlight"}
          className="w-full rounded-lg border border-border px-4 py-2 text-sm hover:bg-accent"
          onClick={handleTorchToggle}
        >
          {torchOn ? "Turn off flashlight" : "Turn on flashlight"}
        </button>
      )}
    </div>
  );
}
