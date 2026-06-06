import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ── Global stubs (hoisted above dynamic import) ─────────────────────────────

const mockGetUserMedia = vi.fn();
Object.defineProperty(global.navigator, "mediaDevices", {
  value: { getUserMedia: mockGetUserMedia },
  configurable: true,
});

HTMLVideoElement.prototype.play = vi.fn().mockResolvedValue(undefined);

const mockBarcodeDetectorDetect = vi.fn();
const MockBarcodeDetector = vi.fn(() => ({ detect: mockBarcodeDetectorDetect }));
(global as unknown as Record<string, unknown>).BarcodeDetector = MockBarcodeDetector;

global.URL.createObjectURL = vi.fn().mockReturnValue("blob:mock-url");
global.URL.revokeObjectURL = vi.fn();

// jsdom does not implement ImageData
(global as unknown as Record<string, unknown>).ImageData = class {
  data: Uint8ClampedArray;
  width: number;
  height: number;
  constructor(data: Uint8ClampedArray, width: number, height: number) {
    this.data = data;
    this.width = width;
    this.height = height;
  }
};

HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
  drawImage: vi.fn(),
  getImageData: vi.fn().mockReturnValue({
    data: new Uint8ClampedArray(64),
    width: 4,
    height: 4,
  }),
  putImageData: vi.fn(),
}) as unknown as typeof HTMLCanvasElement.prototype.getContext;

HTMLCanvasElement.prototype.toDataURL = vi.fn().mockReturnValue("data:image/jpeg;base64,abc");

const mockScanImageData = vi.fn();

vi.mock("@undecaf/zbar-wasm", () => ({
  scanImageData: mockScanImageData,
}));

const { default: BarcodeScanner } = await import("../BarcodeScanner");

// ── Helpers ─────────────────────────────────────────────────────────────────

function makeMockStream(opts: { torch?: boolean } = {}): MediaStream {
  const mockTrack = {
    stop: vi.fn(),
    getCapabilities: vi.fn().mockReturnValue(opts.torch ? { torch: true } : {}),
    applyConstraints: vi.fn().mockResolvedValue(undefined),
  } as unknown as MediaStreamTrack;
  return {
    getTracks: () => [mockTrack],
    getVideoTracks: () => [mockTrack],
  } as unknown as MediaStream;
}

function fireCanPlay(videoEl: HTMLVideoElement) {
  Object.defineProperty(videoEl, "videoWidth", { value: 4, configurable: true });
  Object.defineProperty(videoEl, "videoHeight", { value: 4, configurable: true });
  fireEvent.canPlay(videoEl);
}

// Advance fake setInterval past one tick and drain async callbacks
async function advanceDecode() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(DECODE_INTERVAL_MS + 50);
  });
}

const DECODE_INTERVAL_MS = 300;

// ── Tests ────────────────────────────────────────────────────────────────────

describe("BarcodeScanner", () => {
  beforeEach(() => {
    // Only fake setInterval/clearInterval so React scheduler and waitFor still work
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    vi.clearAllMocks();
    mockGetUserMedia.mockResolvedValue(makeMockStream());
    mockBarcodeDetectorDetect.mockResolvedValue([]);
    mockScanImageData.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders a video element on mount", async () => {
    render(<BarcodeScanner onDetected={vi.fn()} />);
    await waitFor(() => expect(document.querySelector("video")).not.toBeNull());
  });

  it("shows guide overlay and status text after canPlay", async () => {
    render(<BarcodeScanner onDetected={vi.fn()} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    await act(async () => { fireCanPlay(video); });
    await waitFor(() => {
      expect(screen.getByText("Align barcode with the frame")).toBeDefined();
    });
  });

  it("calls onDetected via BarcodeDetector (primary path)", async () => {
    mockBarcodeDetectorDetect.mockResolvedValue([{ rawValue: "8718309975563" }]);
    const onDetected = vi.fn();

    render(<BarcodeScanner onDetected={onDetected} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    await act(async () => { fireCanPlay(video); });

    await advanceDecode();

    expect(onDetected).toHaveBeenCalledWith("8718309975563");
  });

  it("calls onDetected via ZBar WASM when BarcodeDetector returns no results", async () => {
    mockScanImageData.mockResolvedValue([{ decode: () => "1234567890128", typeName: "ZBAR_EAN13" }]);
    const onDetected = vi.fn();

    render(<BarcodeScanner onDetected={onDetected} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    await act(async () => { fireCanPlay(video); });

    await advanceDecode();

    expect(onDetected).toHaveBeenCalledWith("1234567890128");
  });

  it("calls onDetected via ZBar WASM when BarcodeDetector is absent", async () => {
    const savedDetector = (global as unknown as Record<string, unknown>).BarcodeDetector;
    delete (global as unknown as Record<string, unknown>).BarcodeDetector;

    mockScanImageData.mockResolvedValue([{ decode: () => "5901234123457", typeName: "ZBAR_EAN13" }]);
    const onDetected = vi.fn();

    render(<BarcodeScanner onDetected={onDetected} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    await act(async () => { fireCanPlay(video); });

    await advanceDecode();

    expect(onDetected).toHaveBeenCalledWith("5901234123457");

    (global as unknown as Record<string, unknown>).BarcodeDetector = savedDetector;
  });

  it("stops decode loop after successful detection", async () => {
    mockScanImageData.mockResolvedValue([{ decode: () => "5901234123457", typeName: "ZBAR_EAN13" }]);
    const onDetected = vi.fn();

    render(<BarcodeScanner onDetected={onDetected} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    await act(async () => { fireCanPlay(video); });

    // Advance past two interval ticks
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DECODE_INTERVAL_MS * 2 + 100);
    });

    // onDetected called exactly once — interval was cleared after first success
    expect(onDetected).toHaveBeenCalledTimes(1);
  });

  it("shows permission denied error when getUserMedia rejects with NotAllowedError", async () => {
    mockGetUserMedia.mockRejectedValue(
      new DOMException("Permission denied", "NotAllowedError"),
    );

    render(<BarcodeScanner onDetected={vi.fn()} />);

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert.textContent).toContain("Camera permission denied");
    });
  });

  it("shows generic camera error on other getUserMedia failures", async () => {
    mockGetUserMedia.mockRejectedValue(new Error("Device not found"));

    render(<BarcodeScanner onDetected={vi.fn()} />);

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert.textContent).toContain("Failed to start camera");
    });
  });

  it("stops stream tracks on unmount", async () => {
    const stream = makeMockStream();
    const track = stream.getTracks()[0];
    mockGetUserMedia.mockResolvedValue(stream);

    const { unmount } = render(<BarcodeScanner onDetected={vi.fn()} />);
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());

    unmount();

    expect(track.stop).toHaveBeenCalled();
  });

  it("shows torch button when device supports it", async () => {
    mockGetUserMedia.mockResolvedValue(makeMockStream({ torch: true }));

    render(<BarcodeScanner onDetected={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /flashlight/i })).toBeDefined();
    });
  });

  it("toggles torch on and off", async () => {
    const stream = makeMockStream({ torch: true });
    const track = stream.getVideoTracks()[0] as MediaStreamTrack & { applyConstraints: ReturnType<typeof vi.fn> };
    mockGetUserMedia.mockResolvedValue(stream);

    render(<BarcodeScanner onDetected={vi.fn()} />);
    await waitFor(() => screen.getByRole("button", { name: /Turn on flashlight/i }));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Turn on flashlight/i }));
    });

    expect(track.applyConstraints).toHaveBeenCalledWith({
      advanced: [{ torch: true }],
    });
    await waitFor(() => screen.getByRole("button", { name: /Turn off flashlight/i }));
  });
});
