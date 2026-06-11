"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { createAuthBrowserClient } from "@/lib/supabase";
import {
  deleteInventoryItem,
  listInventory,
  updateInventoryItem,
  type InventoryItem,
  type InventoryItemUpdateResponse,
} from "@/lib/inventory";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

type Location = "fridge" | "freezer" | "pantry" | "other";

const LOCATION_LABELS: Record<Location, string> = {
  fridge: "Fridge",
  freezer: "Freezer",
  pantry: "Pantry",
  other: "Other",
};

const STATUS_CYCLE: Record<string, "ok" | "low" | "out"> = {
  ok: "low",
  low: "out",
  out: "ok",
};

type RemoveReason = "used" | "thrown" | "transferred";

const REMOVE_REASONS: Array<{ value: RemoveReason; label: string }> = [
  { value: "used", label: "Used it up" },
  { value: "thrown", label: "Throwing it away" },
  { value: "transferred", label: "Transferring it" },
];

interface GroupItem {
  id: string;
  name: string;
}

async function fetchAccessToken(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function fetchGroups(): Promise<GroupItem[]> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/groups`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to load groups: ${response.status}`);
  return response.json() as Promise<GroupItem[]>;
}

function isUseSoon(expiryDate: string | null): boolean {
  if (!expiryDate) return false;
  const [dd, mm, yyyy] = expiryDate.split("-").map(Number);
  const expiry = new Date(yyyy, mm - 1, dd);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diffMs = expiry.getTime() - today.getTime();
  const diffDays = diffMs / (1000 * 60 * 60 * 24);
  return diffDays >= 0 && diffDays <= 3;
}

function groupByLocation(items: InventoryItem[]): Map<Location, InventoryItem[]> {
  const groups = new Map<Location, InventoryItem[]>();
  for (const item of items) {
    const loc = item.location as Location;
    if (!groups.has(loc)) groups.set(loc, []);
    groups.get(loc)!.push(item);
  }
  return groups;
}

export default function InventoryPage() {
  const searchParams = useSearchParams();
  const groupId = searchParams.get("group");

  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(groupId);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [removeTarget, setRemoveTarget] = useState<InventoryItem | null>(null);
  const [removeReason, setRemoveReason] = useState<RemoveReason>("used");

  // Auto-hide the toast after 3 seconds
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(timer);
  }, [toast]);

  // Load groups if no groupId in URL
  useEffect(() => {
    if (selectedGroupId) return;
    fetchGroups()
      .then((gs) => {
        setGroups(gs);
        if (gs.length === 1) setSelectedGroupId(gs[0].id);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load groups");
      });
  }, [selectedGroupId]);

  // Load inventory when group is selected
  useEffect(() => {
    if (!selectedGroupId) return;
    setLoading(true);
    fetchAccessToken()
      .then((token) => {
        if (!token) throw new Error("Not authenticated");
        return listInventory(selectedGroupId, token);
      })
      .then((data) => {
        setItems(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load inventory");
        setLoading(false);
      });
  }, [selectedGroupId]);

  const handleCycleStatus = useCallback(async (item: InventoryItem) => {
    const nextStatus = STATUS_CYCLE[item.status];
    // Optimistic update
    setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, status: nextStatus } : i)));

    try {
      const token = await fetchAccessToken();
      if (!token) throw new Error("Not authenticated");
      const updated: InventoryItemUpdateResponse = await updateInventoryItem(
        item.id,
        { status: nextStatus },
        token
      );
      setItems((prev) => prev.map((i) => (i.id === item.id ? updated : i)));
      if (updated.shopping_item_created) {
        setToast(`Added ${updated.shopping_item_name} to your shopping list`);
      }
    } catch {
      // Revert on error
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, status: item.status } : i)));
      setError("Failed to update status");
    }
  }, []);

  const handleOpenRemove = useCallback((item: InventoryItem) => {
    setRemoveReason("used");
    setRemoveTarget(item);
  }, []);

  const handleConfirmRemove = useCallback(async () => {
    if (!removeTarget) return;
    const target = removeTarget;
    const reason = removeReason;
    setRemoveTarget(null);
    // Optimistic removal with revert on error
    setItems((prev) => prev.filter((i) => i.id !== target.id));

    try {
      const token = await fetchAccessToken();
      if (!token) throw new Error("Not authenticated");
      await deleteInventoryItem(target.id, { removed_reason: reason }, token);
    } catch {
      setItems((prev) => [...prev, target]);
      setError("Failed to remove item");
    }
  }, [removeTarget, removeReason]);

  // ── Group picker ───────────────────────────────────────────────────────────

  if (!selectedGroupId) {
    return (
      <main className="mx-auto max-w-md p-4">
        <h1 className="mb-4 text-xl font-semibold">Inventory</h1>
        {error && <p className="mb-3 text-sm text-destructive">{error}</p>}
        <p className="mb-3 text-sm text-muted-foreground">Select a household:</p>
        <ul className="space-y-2">
          {groups.map((g) => (
            <li key={g.id}>
              <button
                className="w-full rounded-lg border border-border px-4 py-3 text-left hover:bg-accent"
                onClick={() => setSelectedGroupId(g.id)}
              >
                {g.name}
              </button>
            </li>
          ))}
        </ul>
      </main>
    );
  }

  // ── Loading / error ────────────────────────────────────────────────────────

  if (loading) {
    return (
      <main className="mx-auto max-w-md p-4">
        <p className="text-center text-muted-foreground">Loading inventory…</p>
      </main>
    );
  }

  // ── Inventory list ─────────────────────────────────────────────────────────

  const useSoonItems = items.filter((i) => isUseSoon(i.expiry_date));
  const useSoonIds = new Set(useSoonItems.map((i) => i.id));
  const locationGroups = groupByLocation(items.filter((i) => !useSoonIds.has(i.id)));

  const LOCATION_ORDER: Location[] = ["fridge", "freezer", "pantry", "other"];

  const scanHref = selectedGroupId ? `/inventory/scan?group=${selectedGroupId}` : "/inventory/scan";

  return (
    <main className="mx-auto max-w-md p-4 pb-24">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Inventory</h1>
        <Link
          href={scanHref}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          + Scan
        </Link>
      </div>

      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}

      {useSoonItems.length > 0 && (
        <section role="status" className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
          <h2 className="mb-2 text-sm font-semibold text-amber-800">Use soon</h2>
          <ul className="space-y-1">
            {useSoonItems.map((item) => (
              <li
                key={item.id}
                className={`flex items-center gap-1 ${item.status === "out" ? "line-through opacity-40" : ""}`}
              >
                <button
                  aria-label={`Cycle status for ${item.name}`}
                  className="flex flex-1 items-center justify-between rounded px-2 py-1 text-left text-sm hover:bg-amber-100"
                  onClick={() => handleCycleStatus(item)}
                >
                  <span>{item.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {item.expiry_date} · {item.status}
                  </span>
                </button>
                <button
                  aria-label={`Remove ${item.name}`}
                  className="shrink-0 rounded px-2 py-1 text-muted-foreground hover:bg-amber-100 hover:text-foreground"
                  onClick={() => handleOpenRemove(item)}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {LOCATION_ORDER.filter((loc) => locationGroups.has(loc)).map((loc) => {
        const groupItems = locationGroups.get(loc)!;
        const activeItems = groupItems.filter((i) => i.status !== "out");
        const outItems = groupItems.filter((i) => i.status === "out");

        return (
          <section key={loc} className="mb-4">
            <h2 className="mb-2 text-sm font-semibold text-muted-foreground">
              {LOCATION_LABELS[loc]}
            </h2>
            <ul className="space-y-1">
              {[...activeItems, ...outItems].map((item) => (
                <li
                  key={item.id}
                  className={`flex items-center gap-1 ${
                    item.status === "out" ? "line-through opacity-40" : ""
                  }`}
                >
                  <button
                    aria-label={`Cycle status for ${item.name}`}
                    className="flex flex-1 items-center justify-between rounded-lg border border-border px-3 py-2 text-left text-sm hover:bg-accent"
                    onClick={() => handleCycleStatus(item)}
                  >
                    <span>{item.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {item.expiry_date ?? "no expiry"} · {item.status}
                    </span>
                  </button>
                  <button
                    aria-label={`Remove ${item.name}`}
                    className="shrink-0 rounded px-2 py-2 text-muted-foreground hover:bg-accent hover:text-foreground"
                    onClick={() => handleOpenRemove(item)}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          </section>
        );
      })}

      {items.length === 0 && (
        <p className="text-center text-sm text-muted-foreground">No items yet.</p>
      )}

      <div aria-live="polite">
        {toast && (
          <div className="fixed bottom-20 left-1/2 -translate-x-1/2 rounded-lg bg-foreground px-4 py-2 text-sm text-background shadow-lg">
            {toast}
          </div>
        )}
      </div>

      {removeTarget && (
        <div
          role="dialog"
          aria-label={`Remove ${removeTarget.name}`}
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center"
        >
          <div className="w-full max-w-md rounded-lg bg-background p-4 shadow-lg">
            <h2 className="mb-3 text-base font-semibold">Remove {removeTarget.name}?</h2>
            <fieldset className="mb-4 space-y-2">
              <legend className="sr-only">Removal reason</legend>
              {REMOVE_REASONS.map(({ value, label }) => (
                <label key={value} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="remove-reason"
                    value={value}
                    checked={removeReason === value}
                    onChange={() => setRemoveReason(value)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>
            <div className="flex gap-3">
              <button
                className="flex-1 rounded-lg border border-border px-4 py-2 text-sm hover:bg-accent"
                onClick={() => setRemoveTarget(null)}
              >
                Cancel
              </button>
              <button
                className="flex-1 rounded-lg bg-destructive px-4 py-2 text-sm text-destructive-foreground hover:bg-destructive/90"
                onClick={handleConfirmRemove}
              >
                Remove
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
