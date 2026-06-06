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
// Guide region: centre 80 % wide × 35 % tall
const GUIDE = { xRatio: 0.15, yRatio: 0.325, wRatio: 0.7, hRatio: 0.35 };

export default function BarcodeScanner({ onDetected }: BarcodeScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onDetectedRef = useRef(onDetected);
  const activeRef = useRef(true);
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
        formats: ["ean_13", "ean_8", "upc_a", "code_128"],
      });
    }
    import("@undecaf/zbar-wasm").then((m) => {
      scanImageDataRef.current = m.scanImageData as ScanImageDataFn;
    });
  }, []);

  // Camera setup and cleanup
  useEffect(() => {
    activeRef.current = true;

    navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
      })
      .then((stream) => {
        if (!activeRef.current) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
        const track = stream.getVideoTracks()[0];
        const caps = track?.getCapabilities?.() as Record<string, unknown> | undefined;
        if (caps?.torch) setTorchSupported(true);
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
  }, []);

  const startDecodeLoop = useCallback(() => {
    if (intervalRef.current !== null) return;

    intervalRef.current = setInterval(async () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || !activeRef.current) return;
      if (video.videoWidth === 0) return;

      // 1. Native BarcodeDetector — fast, OS-level, handles curved surfaces well
      if (barcodeDetectorRef.current) {
        try {
          const results = await barcodeDetectorRef.current.detect(video);
          if (results.length > 0 && activeRef.current) {
            clearInterval(intervalRef.current!);
            intervalRef.current = null;
            onDetectedRef.current(results[0].rawValue);
            return;
          }
        } catch { /* fall through to ZBar */ }
      }

      // 2. ZBar WASM on guide-region crop
      const fn = scanImageDataRef.current;
      if (!fn) return;

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(video, 0, 0);

      const gx = Math.round(canvas.width * GUIDE.xRatio);
      const gy = Math.round(canvas.height * GUIDE.yRatio);
      const gw = Math.round(canvas.width * GUIDE.wRatio);
      const gh = Math.round(canvas.height * GUIDE.hRatio);
      const imageData = ctx.getImageData(gx, gy, gw, gh);

      const symbols = await fn(imageData);
      if (symbols.length > 0 && activeRef.current) {
        clearInterval(intervalRef.current!);
        intervalRef.current = null;
        onDetectedRef.current(symbols[0].decode());
      }
    }, DECODE_INTERVAL_MS);
  }, []);

  const handleCanPlay = useCallback(() => {
    setPhase("scanning");
    startDecodeLoop();
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
          onCanPlay={handleCanPlay}
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
        <p className="text-center text-xs text-muted-foreground">
          Align barcode with the frame
        </p>
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
