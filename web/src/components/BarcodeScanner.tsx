"use client";

import { useCallback, useEffect, useRef, useState } from "react";

declare class BarcodeDetector {
  constructor(options?: { formats: string[] });
  detect(image: CanvasImageSource): Promise<Array<{ rawValue: string }>>;
}

interface BarcodeScannerProps {
  onDetected: (barcode: string) => void;
}

type ScanState =
  | { phase: "idle" }
  | { phase: "capturing" }
  | { phase: "decoding"; previewUrl: string }
  | { phase: "failed"; previewUrl: string };

// ── Pixel-level helpers ───────────────────────────────────────────────────────

function toGrayscale(data: Uint8ClampedArray, gray: Uint8Array): void {
  for (let i = 0; i < gray.length; i++) {
    gray[i] = Math.round(
      0.299 * data[i * 4] + 0.587 * data[i * 4 + 1] + 0.114 * data[i * 4 + 2],
    );
  }
}

function writeGray(ctx: CanvasRenderingContext2D, gray: Uint8Array, w: number, h: number): void {
  const out = new Uint8ClampedArray(gray.length * 4);
  for (let i = 0; i < gray.length; i++) {
    out[i * 4] = out[i * 4 + 1] = out[i * 4 + 2] = gray[i];
    out[i * 4 + 3] = 255;
  }
  ctx.putImageData(new ImageData(out, w, h), 0, 0);
}

// Bradley adaptive threshold — O(n) via integral image, handles per-region lighting
function adaptiveThreshold(gray: Uint8Array, w: number, h: number): Uint8Array {
  const integral = new Float64Array(w * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const idx = y * w + x;
      integral[idx] =
        gray[idx] +
        (x > 0 ? integral[idx - 1] : 0) +
        (y > 0 ? integral[idx - w] : 0) -
        (x > 0 && y > 0 ? integral[idx - w - 1] : 0);
    }
  }
  const s = Math.max(1, Math.floor(Math.min(w, h) / 8));
  const binary = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const x1 = Math.max(0, x - s), y1 = Math.max(0, y - s);
      const x2 = Math.min(w - 1, x + s), y2 = Math.min(h - 1, y + s);
      const count = (x2 - x1 + 1) * (y2 - y1 + 1);
      const sum =
        integral[y2 * w + x2] -
        (y1 > 0 ? integral[(y1 - 1) * w + x2] : 0) -
        (x1 > 0 ? integral[y2 * w + x1 - 1] : 0) +
        (x1 > 0 && y1 > 0 ? integral[(y1 - 1) * w + x1 - 1] : 0);
      binary[y * w + x] = gray[y * w + x] * count < sum * 0.85 ? 0 : 255;
    }
  }
  return binary;
}

// ── Canvas transforms ─────────────────────────────────────────────────────────

function applyGrayscaleContrast(ctx: CanvasRenderingContext2D, w: number, h: number): void {
  const src = ctx.getImageData(0, 0, w, h);
  const gray = new Uint8Array(w * h);
  toGrayscale(src.data, gray);
  for (let i = 0; i < gray.length; i++) {
    gray[i] = Math.min(255, Math.max(0, (gray[i] - 128) * 1.5 + 128));
  }
  writeGray(ctx, gray, w, h);
}

function applyAdaptiveThreshold(ctx: CanvasRenderingContext2D, w: number, h: number): void {
  const src = ctx.getImageData(0, 0, w, h);
  const gray = new Uint8Array(w * h);
  toGrayscale(src.data, gray);
  writeGray(ctx, adaptiveThreshold(gray, w, h), w, h);
}

function applySharpen(ctx: CanvasRenderingContext2D, w: number, h: number): void {
  const src = ctx.getImageData(0, 0, w, h);
  const gray = new Uint8Array(w * h);
  toGrayscale(src.data, gray);
  const kernel = [0, -1, 0, -1, 5, -1, 0, -1, 0];
  const out = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let v = 0;
      for (let ky = -1; ky <= 1; ky++) {
        for (let kx = -1; kx <= 1; kx++) {
          v +=
            kernel[(ky + 1) * 3 + (kx + 1)] *
            gray[Math.min(h - 1, Math.max(0, y + ky)) * w + Math.min(w - 1, Math.max(0, x + kx))];
        }
      }
      const i = (y * w + x) * 4;
      out[i] = out[i + 1] = out[i + 2] = Math.min(255, Math.max(0, v));
      out[i + 3] = 255;
    }
  }
  ctx.putImageData(new ImageData(out, w, h), 0, 0);
}

function applyInversion(ctx: CanvasRenderingContext2D, w: number, h: number): void {
  const src = ctx.getImageData(0, 0, w, h);
  for (let i = 0; i < src.data.length; i += 4) {
    src.data[i] = 255 - src.data[i];
    src.data[i + 1] = 255 - src.data[i + 1];
    src.data[i + 2] = 255 - src.data[i + 2];
  }
  ctx.putImageData(src, 0, 0);
}

// ── Barcode region locator ────────────────────────────────────────────────────

interface BBox { x: number; y: number; w: number; h: number }

// Finds the bounding box of the barcode using horizontal transition density.
// Barcodes produce far more dark↔light transitions per row than any other label region.
function findBarcodeBbox(binary: Uint8Array, imgW: number, imgH: number): BBox | null {
  const rowDensity = new Float32Array(imgH);
  for (let y = 0; y < imgH; y++) {
    let t = 0;
    for (let x = 1; x < imgW; x++) {
      if (binary[y * imgW + x] !== binary[y * imgW + x - 1]) t++;
    }
    rowDensity[y] = t / imgW;
  }

  const maxDensity = Math.max(...Array.from(rowDensity));
  if (maxDensity < 0.05) return null;

  const rowThreshold = maxDensity * 0.35;

  // Largest contiguous band of high-density rows
  let bestStart = 0, bestEnd = 0, bestLen = 0, curStart = -1;
  for (let y = 0; y <= imgH; y++) {
    const active = y < imgH && rowDensity[y] >= rowThreshold;
    if (active && curStart === -1) { curStart = y; }
    if (!active && curStart !== -1) {
      if (y - curStart > bestLen) { bestStart = curStart; bestEnd = y - 1; bestLen = y - curStart; }
      curStart = -1;
    }
  }
  if (bestLen < 5) return null;

  // Horizontal extent within barcode rows
  const colCounts = new Uint32Array(imgW);
  for (let y = bestStart; y <= bestEnd; y++) {
    for (let x = 1; x < imgW; x++) {
      if (binary[y * imgW + x] !== binary[y * imgW + x - 1]) colCounts[x]++;
    }
  }
  const maxCol = Math.max(...Array.from(colCounts));
  if (maxCol === 0) return null;

  const colThreshold = maxCol * 0.15;
  let xLeft = imgW, xRight = 0;
  for (let x = 0; x < imgW; x++) {
    if (colCounts[x] >= colThreshold) {
      if (x < xLeft) xLeft = x;
      if (x > xRight) xRight = x;
    }
  }
  if (xRight <= xLeft) return null;

  const padX = Math.max(10, Math.round((xRight - xLeft) * 0.08));
  const padY = Math.max(5, Math.round((bestEnd - bestStart) * 0.15));
  return {
    x: Math.max(0, xLeft - padX),
    y: Math.max(0, bestStart - padY),
    w: Math.min(imgW, xRight - xLeft + padX * 2 + 1),
    h: Math.min(imgH, bestEnd - bestStart + padY * 2 + 1),
  };
}

// ── Scale helper ──────────────────────────────────────────────────────────────

function scaleCanvas(src: HTMLCanvasElement, factor: number): HTMLCanvasElement {
  const dst = document.createElement("canvas");
  dst.width = Math.round(src.width * factor);
  dst.height = Math.round(src.height * factor);
  const ctx = dst.getContext("2d");
  if (ctx) {
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(src, 0, 0, dst.width, dst.height);
  }
  return dst;
}

// ── ZXing error helper ────────────────────────────────────────────────────────

function isZxingNotFound(err: unknown): boolean {
  return (err as { constructor?: { kind?: string } }).constructor?.kind !== undefined;
}

// ── Main decode pipeline ──────────────────────────────────────────────────────

async function attemptDecode(
  canvas: HTMLCanvasElement,
  scratchCanvas: HTMLCanvasElement,
): Promise<string | null> {
  const { width, height } = canvas;

  // 1. Native BarcodeDetector (Chrome 83+, Android WebView)
  if ("BarcodeDetector" in window) {
    try {
      const detector = new BarcodeDetector({
        formats: ["ean_13", "ean_8", "upc_a", "code_128"],
      });
      const results = await detector.detect(canvas);
      if (results.length > 0) return results[0].rawValue;
    } catch { /* fall through */ }
  }

  const [{ BrowserMultiFormatReader }, { DecodeHintType, BarcodeFormat }] =
    await Promise.all([import("@zxing/browser"), import("@zxing/library")]);

  const hints = new Map<number, unknown>([
    [
      DecodeHintType.POSSIBLE_FORMATS,
      [BarcodeFormat.EAN_13, BarcodeFormat.EAN_8, BarcodeFormat.UPC_A, BarcodeFormat.CODE_128],
    ],
    [DecodeHintType.TRY_HARDER, true],
  ]);
  const reader = new BrowserMultiFormatReader(hints as never);

  function tryZxing(src: HTMLCanvasElement): string | null {
    try { return reader.decodeFromCanvas(src).getText(); }
    catch (err) { if (!isZxingNotFound(err)) throw err; return null; }
  }

  function prepScratch(transform: (ctx: CanvasRenderingContext2D, w: number, h: number) => void): void {
    scratchCanvas.width = width;
    scratchCanvas.height = height;
    const ctx = scratchCanvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(canvas, 0, 0);
    transform(ctx, width, height);
  }

  // 2. ZXing — original
  const r2 = tryZxing(canvas);
  if (r2) return r2;

  // 3. ZXing — 2x upscale (more pixels per bar, helps both blur and small captures)
  const r3 = tryZxing(scaleCanvas(canvas, 2));
  if (r3) return r3;

  // 4. ZXing — grayscale + global contrast
  prepScratch(applyGrayscaleContrast);
  const r4 = tryZxing(scratchCanvas);
  if (r4) return r4;

  // 5. ZXing — sharpened
  prepScratch(applySharpen);
  const r5 = tryZxing(scratchCanvas);
  if (r5) return r5;

  // 6. ZXing — adaptive threshold (whole image)
  prepScratch(applyAdaptiveThreshold);
  const r6 = tryZxing(scratchCanvas);
  if (r6) return r6;

  // 7–8. Isolation pipeline: find barcode region → crop → normalize → decode
  //
  // Build a binarized view of the image to locate the barcode via transition density.
  // This is independent of lighting gradients from curved surfaces.
  const binaryView = (() => {
    scratchCanvas.width = width;
    scratchCanvas.height = height;
    const ctx = scratchCanvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(canvas, 0, 0);
    const imgData = ctx.getImageData(0, 0, width, height);
    const gray = new Uint8Array(width * height);
    toGrayscale(imgData.data, gray);
    return adaptiveThreshold(gray, width, height);
  })();

  if (binaryView) {
    const bbox = findBarcodeBbox(binaryView, width, height);
    if (bbox && bbox.w > 20 && bbox.h > 10) {
      // Scale crop to a consistent 800px width so bars are ~8px wide for ZXing
      const TARGET_W = 800;
      const cropScale = TARGET_W / bbox.w;
      const cropCanvas = document.createElement("canvas");
      cropCanvas.width = TARGET_W;
      cropCanvas.height = Math.round(bbox.h * cropScale);
      const cropCtx = cropCanvas.getContext("2d");
      if (cropCtx) {
        // 7. Crop from original (not binarized) + scale up
        cropCtx.drawImage(canvas, bbox.x, bbox.y, bbox.w, bbox.h, 0, 0, cropCanvas.width, cropCanvas.height);
        const r7 = tryZxing(cropCanvas);
        if (r7) return r7;

        // 8. Same crop + adaptive threshold (handles lighting gradient within the crop)
        applyAdaptiveThreshold(cropCtx, cropCanvas.width, cropCanvas.height);
        const r8 = tryZxing(cropCanvas);
        if (r8) return r8;
      }
    }
  }

  // 9. ZXing — inverted (last resort for light-on-dark labels)
  prepScratch(applyInversion);
  const r9 = tryZxing(scratchCanvas);
  if (r9) return r9;

  return null;
}

export default function BarcodeScanner({ onDetected }: BarcodeScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const scratchCanvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  const onDetectedRef = useRef(onDetected);

  const [scanState, setScanState] = useState<ScanState>({ phase: "idle" });
  const [cameraError, setCameraError] = useState<string | null>(null);

  useEffect(() => {
    onDetectedRef.current = onDetected;
  });

  useEffect(() => {
    let active = true;

    navigator.mediaDevices
      .getUserMedia({
        video: {
          facingMode: "environment",
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      })
      .then((stream) => {
        if (!active) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
      })
      .catch((err: unknown) => {
        if (!active) return;
        if (err instanceof DOMException && err.name === "NotAllowedError") {
          setCameraError(
            "Camera permission denied. Please allow camera access and try again.",
          );
        } else {
          setCameraError("Failed to start camera.");
        }
      });

    return () => {
      active = false;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = null;
      }
    };
  }, []);

  const handleCanPlay = useCallback(() => {
    setScanState((prev) =>
      prev.phase === "idle" ? { phase: "capturing" } : prev,
    );
  }, []);

  const handleCapture = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const scratchCanvas = scratchCanvasRef.current;
    if (!video || !canvas || !scratchCanvas) return;

    const { videoWidth: w, videoHeight: h } = video;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);

    const previewUrl = canvas.toDataURL("image/jpeg", 0.9);
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = previewUrl;

    setScanState({ phase: "decoding", previewUrl });

    try {
      const barcode = await attemptDecode(canvas, scratchCanvas);
      if (barcode) {
        onDetectedRef.current(barcode);
      } else {
        setScanState({ phase: "failed", previewUrl });
      }
    } catch {
      setScanState({ phase: "failed", previewUrl });
    }
  }, []);

  const handleRetry = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setScanState({ phase: "capturing" });
  }, []);

  if (cameraError) {
    return (
      <div role="alert" className="rounded-lg bg-destructive/10 p-4 text-destructive">
        <p>{cameraError}</p>
      </div>
    );
  }

  const previewUrl =
    scanState.phase === "decoding" || scanState.phase === "failed"
      ? scanState.previewUrl
      : null;

  return (
    <div className="relative space-y-3">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        aria-label="Camera viewfinder"
        className={`w-full rounded-lg ${previewUrl ? "hidden" : ""}`}
        onCanPlay={handleCanPlay}
      />

      <canvas ref={canvasRef} className="hidden" aria-hidden="true" />
      <canvas ref={scratchCanvasRef} className="hidden" aria-hidden="true" />

      {previewUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={previewUrl}
          alt="Captured frame"
          className="w-full rounded-lg"
        />
      )}

      {scanState.phase === "capturing" && (
        <button
          className="w-full rounded-lg bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          onClick={handleCapture}
        >
          Scan
        </button>
      )}

      {scanState.phase === "idle" && (
        <p className="text-center text-xs text-muted-foreground">
          Starting camera…
        </p>
      )}

      {scanState.phase === "decoding" && (
        <p className="text-center text-xs text-muted-foreground">Decoding…</p>
      )}

      {scanState.phase === "failed" && (
        <div className="space-y-2">
          <p role="alert" className="text-center text-sm text-destructive">
            Could not read barcode. Try better lighting or a flatter surface.
          </p>
          <button
            className="w-full rounded-lg bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            onClick={handleRetry}
          >
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
