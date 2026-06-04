/**
 * Failing component tests for BarcodeScanner — must be RED before implementation.
 */
import { render, screen, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockStop = vi.fn();
const mockDecodeFromVideoDevice = vi.fn();

vi.mock("@zxing/browser", () => ({
  BrowserMultiFormatReader: vi.fn(() => ({
    decodeFromVideoDevice: mockDecodeFromVideoDevice,
  })),
}));

// Default: decodeFromVideoDevice resolves with an IScannerControls object
const defaultControls = { stop: mockStop };

// Import after mock declaration so vitest hoists the mock correctly
const { default: BarcodeScanner } = await import("../BarcodeScanner");

describe("BarcodeScanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDecodeFromVideoDevice.mockResolvedValue(defaultControls);
  });

  it("renders a video element", async () => {
    render(<BarcodeScanner onDetected={vi.fn()} />);
    await waitFor(() => {
      expect(document.querySelector("video")).not.toBeNull();
    });
  });

  it("calls onDetected with decoded barcode string", async () => {
    const onDetected = vi.fn();
    let capturedCallback:
      | ((result: unknown, err: unknown) => void)
      | null = null;

    mockDecodeFromVideoDevice.mockImplementation(
      async (
        _deviceId: unknown,
        _video: unknown,
        callback: (result: unknown, err: unknown) => void,
      ) => {
        capturedCallback = callback;
        return defaultControls;
      },
    );

    render(<BarcodeScanner onDetected={onDetected} />);

    await waitFor(() => {
      expect(capturedCallback).not.toBeNull();
    });

    act(() => {
      capturedCallback!({ getText: () => "8718309975563" }, null);
    });

    expect(onDetected).toHaveBeenCalledWith("8718309975563");
  });

  it("renders error state when camera permission denied", async () => {
    mockDecodeFromVideoDevice.mockRejectedValue(
      new DOMException("Permission denied", "NotAllowedError"),
    );

    render(<BarcodeScanner onDetected={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeDefined();
    });
  });
});
