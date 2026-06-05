import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// --- Global mocks (must be hoisted above dynamic import) ---

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

HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
  drawImage: vi.fn(),
  getImageData: vi.fn().mockReturnValue({
    data: new Uint8ClampedArray(16),
    width: 4,
    height: 4,
  }),
  putImageData: vi.fn(),
}) as unknown as typeof HTMLCanvasElement.prototype.getContext;

HTMLCanvasElement.prototype.toDataURL = vi.fn().mockReturnValue("data:image/jpeg;base64,abc");

const mockDecodeFromCanvas = vi.fn();

vi.mock("@zxing/browser", () => ({
  BrowserMultiFormatReader: vi.fn(() => ({
    decodeFromCanvas: mockDecodeFromCanvas,
  })),
}));

vi.mock("@zxing/library", () => ({
  DecodeHintType: { POSSIBLE_FORMATS: 2, TRY_HARDER: 3 },
  BarcodeFormat: { EAN_13: 7, EAN_8: 6, UPC_A: 14, CODE_128: 4 },
}));

const { default: BarcodeScanner } = await import("../BarcodeScanner");

// --- Helpers ---

function makeMockStream(): MediaStream {
  const mockTrack = { stop: vi.fn() } as unknown as MediaStreamTrack;
  return { getTracks: () => [mockTrack] } as unknown as MediaStream;
}

function fireCanPlay(videoEl: HTMLVideoElement) {
  // Use 4×4 matching the mocked getImageData size so pixel-processing loops are trivial
  Object.defineProperty(videoEl, "videoWidth", { value: 4, configurable: true });
  Object.defineProperty(videoEl, "videoHeight", { value: 4, configurable: true });
  fireEvent.canPlay(videoEl);
}

const notFound = Object.assign(new Error("NotFoundException"), {
  constructor: { kind: "NotFoundException" },
});
const throwNotFound = () => { throw notFound; };

// --- Tests ---
//
// ZXing call order in the pipeline (isolation step skipped in tests because
// mock getImageData returns all-zeros → no transitions → null bbox):
//   #1 original | #2 2x-scale | #3 grayscale+contrast | #4 sharpen | #5 adaptive | #6 inverted

describe("BarcodeScanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // mockReset clears once queues that clearAllMocks leaves intact
    mockDecodeFromCanvas.mockReset();
    mockGetUserMedia.mockResolvedValue(makeMockStream());
    mockBarcodeDetectorDetect.mockResolvedValue([]);
    mockDecodeFromCanvas.mockImplementation(throwNotFound);
  });

  it("renders a video element on mount", async () => {
    render(<BarcodeScanner onDetected={vi.fn()} />);
    await waitFor(() => {
      expect(document.querySelector("video")).not.toBeNull();
    });
  });

  it("shows Scan button after canPlay event", async () => {
    render(<BarcodeScanner onDetected={vi.fn()} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    fireCanPlay(video);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Scan" })).toBeDefined();
    });
  });

  it("calls onDetected via BarcodeDetector success path", async () => {
    mockBarcodeDetectorDetect.mockResolvedValue([{ rawValue: "8718309975563" }]);
    const onDetected = vi.fn();

    render(<BarcodeScanner onDetected={onDetected} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    fireCanPlay(video);
    await waitFor(() => screen.getByRole("button", { name: "Scan" }));

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Scan" })); });

    await waitFor(() => { expect(onDetected).toHaveBeenCalledWith("8718309975563"); });
  });

  it("falls back to ZXing (original) when BarcodeDetector returns no results", async () => {
    // call #1 succeeds
    mockDecodeFromCanvas.mockImplementationOnce(() => ({ getText: () => "1234567890128" }));
    const onDetected = vi.fn();

    render(<BarcodeScanner onDetected={onDetected} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    fireCanPlay(video);
    await waitFor(() => screen.getByRole("button", { name: "Scan" }));

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Scan" })); });

    await waitFor(() => { expect(onDetected).toHaveBeenCalledWith("1234567890128"); });
  });

  it("succeeds on 2x-scale fallback (call #2)", async () => {
    mockDecodeFromCanvas
      .mockImplementationOnce(throwNotFound)  // #1 original
      .mockImplementationOnce(() => ({ getText: () => "5901234123457" })); // #2 2x-scale
    const onDetected = vi.fn();

    render(<BarcodeScanner onDetected={onDetected} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    fireCanPlay(video);
    await waitFor(() => screen.getByRole("button", { name: "Scan" }));

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Scan" })); });

    await waitFor(() => { expect(onDetected).toHaveBeenCalledWith("5901234123457"); });
  });

  it("succeeds on grayscale+contrast fallback (call #3)", async () => {
    mockDecodeFromCanvas
      .mockImplementationOnce(throwNotFound)  // #1 original
      .mockImplementationOnce(throwNotFound)  // #2 2x-scale
      .mockImplementation(() => ({ getText: () => "5901234123457" })); // #3+ base → success
    const onDetected = vi.fn();

    render(<BarcodeScanner onDetected={onDetected} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    fireCanPlay(video);
    await waitFor(() => screen.getByRole("button", { name: "Scan" }));

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Scan" })); });

    await waitFor(() => { expect(onDetected).toHaveBeenCalledWith("5901234123457"); });
  });

  it("succeeds on adaptive threshold fallback — curved surface case (call #5)", async () => {
    mockDecodeFromCanvas
      .mockImplementationOnce(throwNotFound)  // #1 original
      .mockImplementationOnce(throwNotFound)  // #2 2x-scale
      .mockImplementationOnce(throwNotFound)  // #3 grayscale+contrast
      .mockImplementationOnce(throwNotFound)  // #4 sharpen
      .mockImplementation(() => ({ getText: () => "8719587223796" })); // #5+ base → success
    const onDetected = vi.fn();

    render(<BarcodeScanner onDetected={onDetected} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    fireCanPlay(video);
    await waitFor(() => screen.getByRole("button", { name: "Scan" }));

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Scan" })); });

    await waitFor(() => { expect(onDetected).toHaveBeenCalledWith("8719587223796"); });
  });

  it("shows failed alert when all pipeline steps fail", async () => {
    // permanent mock → all ZXing calls throw
    render(<BarcodeScanner onDetected={vi.fn()} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    fireCanPlay(video);
    await waitFor(() => screen.getByRole("button", { name: "Scan" }));

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Scan" })); });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeDefined();
      expect(screen.getByRole("button", { name: "Try again" })).toBeDefined();
    });
  });

  it("resets to capturing state on Try again", async () => {
    render(<BarcodeScanner onDetected={vi.fn()} />);
    const video = document.querySelector("video")!;
    await waitFor(() => expect(mockGetUserMedia).toHaveBeenCalled());
    fireCanPlay(video);
    await waitFor(() => screen.getByRole("button", { name: "Scan" }));

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Scan" })); });
    await waitFor(() => screen.getByRole("button", { name: "Try again" }));

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Try again" })); });

    await waitFor(() => { expect(screen.getByRole("button", { name: "Scan" })).toBeDefined(); });
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
});
