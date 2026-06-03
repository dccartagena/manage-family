"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createAuthBrowserClient } from "@/lib/supabase";
import { subscribeToShopping, type ShoppingRealtimePayload } from "@/lib/realtime";
import { drainShoppingQueue, enqueueShoppingMutation } from "@/lib/sync";

interface GroupItem {
  id: string;
  name: string;
  depth: number;
  role: string;
}

interface ShoppingItem {
  id: string;
  group_id: string;
  name: string;
  checked: boolean;
  updated_at: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

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

async function fetchShoppingItems(groupId: string): Promise<ShoppingItem[]> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/groups/${groupId}/shopping`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to load shopping list: ${response.status}`);
  return response.json() as Promise<ShoppingItem[]>;
}

async function patchItem(
  itemId: string,
  payload: { name?: string; checked?: boolean },
): Promise<ShoppingItem> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/shopping/${itemId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Failed to update item: ${response.status}`);
  return response.json() as Promise<ShoppingItem>;
}

async function addItem(groupId: string, name: string): Promise<ShoppingItem> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/groups/${groupId}/shopping`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) throw new Error(`Failed to add item: ${response.status}`);
  return response.json() as Promise<ShoppingItem>;
}

async function deleteItem(itemId: string): Promise<void> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/shopping/${itemId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to delete item: ${response.status}`);
}

export default function ShoppingPage() {
  const router = useRouter();
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string>("");
  const [items, setItems] = useState<ShoppingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [error, setError] = useState("");
  const [isOnline, setIsOnline] = useState(
    typeof navigator !== "undefined" ? navigator.onLine : true,
  );
  const [newItemName, setNewItemName] = useState("");
  const [adding, setAdding] = useState(false);
  const cleanupRealtimeRef = useRef<(() => void) | null>(null);

  const applyRealtimePayload = useCallback((payload: ShoppingRealtimePayload) => {
    const { eventType, new: newRecord, old: oldRecord } = payload;

    if (eventType === "INSERT" && newRecord) {
      const inserted = newRecord as ShoppingItem;
      setItems((prev) => {
        if (prev.some((i) => i.id === inserted.id)) return prev;
        return [...prev, inserted];
      });
    } else if (eventType === "UPDATE" && newRecord) {
      const updated = newRecord as ShoppingItem;
      setItems((prev) =>
        prev.map((i) => (i.id === updated.id ? updated : i)),
      );
    } else if (eventType === "DELETE" && oldRecord) {
      const deleted = oldRecord as { id: string };
      setItems((prev) => prev.filter((i) => i.id !== deleted.id));
    }
  }, []);

  useEffect(() => {
    fetchGroups()
      .then((loadedGroups) => {
        setGroups(loadedGroups);
        if (loadedGroups.length > 0) {
          setSelectedGroupId(loadedGroups[0].id);
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedGroupId) return;

    // Clean up previous subscription
    if (cleanupRealtimeRef.current) {
      cleanupRealtimeRef.current();
      cleanupRealtimeRef.current = null;
    }

    setItemsLoading(true);
    fetchShoppingItems(selectedGroupId)
      .then((loaded) => {
        setItems(loaded);
        // Subscribe to real-time after initial load
        // Approved FR-023 infrastructure exception: Realtime subscription, not a table query
        cleanupRealtimeRef.current = subscribeToShopping(
          selectedGroupId,
          applyRealtimePayload,
        );
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setItemsLoading(false));

    return () => {
      if (cleanupRealtimeRef.current) {
        cleanupRealtimeRef.current();
        cleanupRealtimeRef.current = null;
      }
    };
  }, [selectedGroupId, applyRealtimePayload]);

  // T049: navigator.onLine detection + drain queue on reconnect
  useEffect(() => {
    function handleOnline() {
      setIsOnline(true);
      drainShoppingQueue().catch(() => {});
    }
    function handleOffline() {
      setIsOnline(false);
    }

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  async function handleToggleCheck(item: ShoppingItem) {
    const newChecked = !item.checked;

    // Optimistic update
    setItems((prev) =>
      prev.map((i) => (i.id === item.id ? { ...i, checked: newChecked } : i)),
    );

    try {
      await patchItem(item.id, { checked: newChecked });
    } catch {
      // Revert optimistic update
      setItems((prev) =>
        prev.map((i) => (i.id === item.id ? { ...i, checked: item.checked } : i)),
      );

      if (!isOnline) {
        const token = await fetchAccessToken();
        if (token) {
          await enqueueShoppingMutation({
            itemId: item.id,
            op: "patch",
            payload: { checked: newChecked },
            enqueuedAt: new Date().toISOString(),
            accessToken: token,
          });
          // Re-apply optimistic update after queuing
          setItems((prev) =>
            prev.map((i) =>
              i.id === item.id ? { ...i, checked: newChecked } : i,
            ),
          );
        }
      }
    }
  }

  async function handleAddItem(e: React.FormEvent) {
    e.preventDefault();
    const name = newItemName.trim();
    if (!name || !selectedGroupId) return;

    setAdding(true);
    try {
      const created = await addItem(selectedGroupId, name);
      setItems((prev) => [...prev, created]);
      setNewItemName("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add item");
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(itemId: string) {
    setItems((prev) => prev.filter((i) => i.id !== itemId));
    try {
      await deleteItem(itemId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete item");
      // Re-fetch to restore state on error
      if (selectedGroupId) {
        fetchShoppingItems(selectedGroupId)
          .then(setItems)
          .catch(() => {});
      }
    }
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-md p-6">
        <p className="text-muted-foreground">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-md space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Shopping</h1>
        {!isOnline && (
          <span
            role="status"
            aria-live="polite"
            className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
          >
            Offline
          </span>
        )}
      </div>

      {error && (
        <p
          role="alert"
          className="rounded border border-destructive p-2 text-sm text-destructive"
        >
          {error}
        </p>
      )}

      {groups.length > 1 && (
        <select
          value={selectedGroupId}
          onChange={(e) => setSelectedGroupId(e.target.value)}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          aria-label="Select household"
        >
          {groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
      )}

      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No households yet.{" "}
          <button
            type="button"
            onClick={() => router.push("/groups/new")}
            className="underline"
          >
            Create one
          </button>{" "}
          to start a shopping list.
        </p>
      ) : (
        <>
          <form onSubmit={handleAddItem} className="flex gap-2">
            <input
              type="text"
              value={newItemName}
              onChange={(e) => setNewItemName(e.target.value)}
              placeholder="Add item…"
              aria-label="New shopping item name"
              className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              type="submit"
              disabled={adding || !newItemName.trim()}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              Add
            </button>
          </form>

          {itemsLoading ? (
            <p className="text-sm text-muted-foreground">Loading items…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nothing on the list yet. Add something above.
            </p>
          ) : (
            <ul className="space-y-2">
              {items.map((item) => (
                <li
                  key={item.id}
                  data-checked={item.checked ? "true" : undefined}
                  className={`flex items-center gap-3 rounded-lg border p-3 ${
                    item.checked
                      ? "border-border bg-muted opacity-60"
                      : "border-border bg-card"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => handleToggleCheck(item)}
                    aria-label={item.checked ? `Uncheck ${item.name}` : `Check ${item.name}`}
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 transition-colors ${
                      item.checked
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border"
                    }`}
                  >
                    {item.checked && (
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="12"
                        height="12"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                    <span className="sr-only">{item.checked ? "Checked" : "Unchecked"}</span>
                  </button>

                  <span
                    className={`flex-1 text-sm ${item.checked ? "line-through text-muted-foreground" : ""}`}
                  >
                    {item.name}
                  </span>

                  <button
                    type="button"
                    onClick={() => handleDelete(item.id)}
                    aria-label={`Remove ${item.name}`}
                    className="shrink-0 rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                    <span className="sr-only">Remove</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </main>
  );
}
