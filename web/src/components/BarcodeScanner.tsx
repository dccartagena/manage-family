"use client";

import { useEffect, useRef, useState } from "react";

interface BarcodeScannerProps {
  onDetected: (barcode: string) => void;
}

export default function BarcodeScanner({ onDetected }: BarcodeScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let controls: { stop: () => void } | null = null;

    async function startScanning() {
      try {
        const { BrowserMultiFormatReader } = await import("@zxing/browser");
        const reader = new BrowserMultiFormatReader();

        controls = await reader.decodeFromVideoDevice(
          undefined,
          videoRef.current!,
          (result, err) => {
            if (result) {
              onDetected(result.getText());
            }
            if (
              err &&
              // NotFoundException fires constantly on frames with no barcode — ignore it
              err.name !== "NotFoundException"
            ) {
              setError(err.message);
            }
          },
        );
      } catch (err) {
        if (err instanceof DOMException && err.name === "NotAllowedError") {
          setError(
            "Camera permission denied. Please allow camera access and try again.",
          );
        } else {
          setError("Failed to start camera.");
        }
      }
    }

    startScanning();

    return () => {
      controls?.stop();
    };
  }, [onDetected]);

  if (error) {
    return (
      <div role="alert" className="rounded-lg bg-destructive/10 p-4 text-destructive">
        <p>{error}</p>
      </div>
    );
  }

  return (
    <video
      ref={videoRef}
      aria-label="Barcode scanner camera"
      className="w-full rounded-lg"
    />
  );
}
