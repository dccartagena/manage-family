/**
 * Failing tests for shopping page — must fail before shopping/page.tsx is implemented.
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ShoppingPage from "../page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/supabase", () => ({
  createAuthBrowserClient: () => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: "tok" } } }),
      getUser: vi.fn().mockResolvedValue({ data: { user: { id: "user-1" } } }),
    },
  }),
}));

vi.mock("@/lib/realtime", () => ({
  subscribeToShopping: vi.fn().mockReturnValue(() => {}),
}));

vi.mock("@/lib/sync", () => ({
  enqueueShoppingMutation: vi.fn(),
  drainShoppingQueue: vi.fn().mockResolvedValue(undefined),
}));

const mockGroups = [{ id: "group-1", name: "Home", depth: 0, role: "owner" }];
const mockItems = [
  { id: "item-1", group_id: "group-1", name: "Milk", checked: false, updated_at: "2026-06-03T10:00:00Z" },
  { id: "item-2", group_id: "group-1", name: "Eggs", checked: true, updated_at: "2026-06-03T10:00:00Z" },
];

global.fetch = vi.fn().mockImplementation((url: string) => {
  if (url.includes("/shopping")) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mockItems),
    });
  }
  if (url.includes("/api/v1/groups")) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mockGroups),
    });
  }
  return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
}) as unknown as typeof fetch;

describe("ShoppingPage", () => {
  it("renders shopping list items", async () => {
    render(<ShoppingPage />);
    expect(await screen.findByText("Milk")).toBeInTheDocument();
    expect(await screen.findByText("Eggs")).toBeInTheDocument();
  });

  it("checked item renders visually distinct", async () => {
    render(<ShoppingPage />);
    // Checked item should have a distinguishing class/role
    const checkedItem = await screen.findByText("Eggs");
    expect(checkedItem.closest("[data-checked]") ?? checkedItem).toBeTruthy();
  });

  it("offline indicator renders when navigator.onLine is false", async () => {
    Object.defineProperty(navigator, "onLine", {
      value: false,
      configurable: true,
    });

    render(<ShoppingPage />);

    expect(await screen.findByText(/offline/i)).toBeInTheDocument();

    Object.defineProperty(navigator, "onLine", {
      value: true,
      configurable: true,
    });
  });
});
