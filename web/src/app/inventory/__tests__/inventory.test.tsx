/**
 * Failing component tests for inventory list page — must be RED before T032 implementation.
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { InventoryItem } from "@/lib/inventory";

const mockListInventory = vi.fn<() => Promise<InventoryItem[]>>();
const mockUpdateInventoryItem = vi.fn();
const mockDeleteInventoryItem = vi.fn();

vi.mock("@/lib/inventory", () => ({
  listInventory: (...args: unknown[]) => mockListInventory(...(args as [])),
  updateInventoryItem: (...args: unknown[]) => mockUpdateInventoryItem(...args),
  deleteInventoryItem: (...args: unknown[]) => mockDeleteInventoryItem(...args),
}));

vi.mock("@/lib/supabase", () => ({
  createAuthBrowserClient: vi.fn(() => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  })),
}));

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
  useSearchParams: vi.fn(() => ({
    get: vi.fn((key: string) => (key === "group" ? "group-1" : null)),
  })),
}));

function daysFromNow(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}-${mm}-${d.getFullYear()}`;
}

function makeItem(overrides: Partial<InventoryItem> & { id: string }): InventoryItem {
  return {
    id: overrides.id,
    group_id: "group-1",
    canonical_product_id: "cp-1",
    canonical_product_name: "Milk",
    barcode: null,
    name: "Test Item",
    location: "fridge",
    status: "ok",
    expiry_date: null,
    added_by: "person-1",
    added_at: "2026-06-04T10:00:00Z",
    ...overrides,
  };
}

const { default: InventoryPage } = await import("../page");

describe("InventoryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders use-soon section with amber class for items expiring within 3 days", async () => {
    mockListInventory.mockResolvedValue([
      makeItem({ id: "1", name: "Expiring Soon", expiry_date: daysFromNow(1), location: "fridge" }),
      makeItem({ id: "2", name: "Fine Item", expiry_date: daysFromNow(10), location: "pantry" }),
    ]);

    render(<InventoryPage />);

    await waitFor(() => {
      const useSoonSection = screen.getByRole("status");
      expect(useSoonSection.className).toMatch(/bg-amber-50/);
      expect(screen.getByText("Expiring Soon")).toBeDefined();
    });
  });

  it("does not render use-soon section when no items expire within 3 days", async () => {
    mockListInventory.mockResolvedValue([
      makeItem({ id: "1", name: "Fine Item", expiry_date: daysFromNow(10), location: "fridge" }),
    ]);

    render(<InventoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Fine Item")).toBeDefined();
    });

    expect(screen.queryByRole("status")).toBeNull();
  });

  it("renders items in location groups with group headings", async () => {
    mockListInventory.mockResolvedValue([
      makeItem({ id: "1", name: "Fridge Item", location: "fridge" }),
      makeItem({ id: "2", name: "Pantry Item", location: "pantry" }),
      makeItem({ id: "3", name: "Freezer Item", location: "freezer" }),
    ]);

    render(<InventoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Fridge")).toBeDefined();
      expect(screen.getByText("Pantry")).toBeDefined();
      expect(screen.getByText("Freezer")).toBeDefined();
      expect(screen.getByText("Fridge Item")).toBeDefined();
      expect(screen.getByText("Pantry Item")).toBeDefined();
      expect(screen.getByText("Freezer Item")).toBeDefined();
    });
  });

  it("renders out items with ghost/muted opacity class", async () => {
    mockListInventory.mockResolvedValue([
      makeItem({ id: "1", name: "Out Item", status: "out", location: "fridge" }),
      makeItem({ id: "2", name: "Ok Item", status: "ok", location: "fridge" }),
    ]);

    render(<InventoryPage />);

    await waitFor(() => {
      const outLi = screen.getByText("Out Item").closest("li");
      expect(outLi?.className).toMatch(/opacity-40/);
      const okLi = screen.getByText("Ok Item").closest("li");
      expect(okLi?.className).not.toMatch(/opacity-40/);
    });
  });

  it("cycles status when item button is tapped", async () => {
    mockListInventory.mockResolvedValue([
      makeItem({ id: "1", name: "Cycle Item", status: "ok", location: "fridge" }),
    ]);
    mockUpdateInventoryItem.mockResolvedValue(
      makeItem({
        id: "1",
        name: "Cycle Item",
        status: "low",
        location: "fridge",
        shopping_item_created: false,
        shopping_item_name: null,
      } as InventoryItem)
    );

    render(<InventoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Cycle Item")).toBeDefined();
    });

    const cycleBtn = screen.getByLabelText("Cycle status for Cycle Item");
    fireEvent.click(cycleBtn);

    await waitFor(() => {
      expect(mockUpdateInventoryItem).toHaveBeenCalledWith("1", { status: "low" }, "test-token");
    });
  });

  // T036: shopping list auto-add toast
  it("shows toast when a staple status change adds it to the shopping list", async () => {
    mockListInventory.mockResolvedValue([
      makeItem({ id: "1", name: "Milk Carton", status: "ok", location: "fridge" }),
    ]);
    mockUpdateInventoryItem.mockResolvedValue(
      makeItem({
        id: "1",
        name: "Milk Carton",
        status: "low",
        location: "fridge",
        shopping_item_created: true,
        shopping_item_name: "Milk",
      } as InventoryItem)
    );

    render(<InventoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Milk Carton")).toBeDefined();
    });

    fireEvent.click(screen.getByLabelText("Cycle status for Milk Carton"));

    await waitFor(() => {
      expect(screen.getByText("Added Milk to your shopping list")).toBeDefined();
    });
  });

  // T038: removal reason dialog
  it("renders removal dialog with three reasons and 'used' pre-selected", async () => {
    mockListInventory.mockResolvedValue([
      makeItem({ id: "1", name: "Old Cheese", location: "fridge" }),
    ]);

    render(<InventoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Old Cheese")).toBeDefined();
    });

    fireEvent.click(screen.getByLabelText("Remove Old Cheese"));

    const used = screen.getByLabelText("Used it up") as HTMLInputElement;
    expect(screen.getByLabelText("Throwing it away")).toBeDefined();
    expect(screen.getByLabelText("Transferring it")).toBeDefined();
    expect(used.checked).toBe(true);
  });

  it("confirm calls deleteInventoryItem with the selected reason", async () => {
    mockListInventory.mockResolvedValue([
      makeItem({ id: "1", name: "Old Cheese", location: "fridge" }),
    ]);
    mockDeleteInventoryItem.mockResolvedValue(undefined);

    render(<InventoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Old Cheese")).toBeDefined();
    });

    fireEvent.click(screen.getByLabelText("Remove Old Cheese"));
    fireEvent.click(screen.getByLabelText("Throwing it away"));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() => {
      expect(mockDeleteInventoryItem).toHaveBeenCalledWith(
        "1",
        { removed_reason: "thrown" },
        "test-token"
      );
    });
  });
});
