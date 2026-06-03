/**
 * IndexedDB offline mutation queue for shopping items.
 * Mutations queued when offline; replayed in order on reconnect.
 * Last-write-wins merge: skip queued op if server's updated_at is newer.
 */
const DB_NAME = "household-sync";
const DB_VERSION = 1;
const STORE_NAME = "shopping-queue";

interface ShoppingMutation {
  id: string;
  itemId: string;
  op: "patch";
  payload: { name?: string; checked?: boolean };
  enqueuedAt: string;
  accessToken: string;
}

interface ShoppingItemRecord {
  updated_at: string;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE_NAME, { keyPath: "id" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function enqueueShoppingMutation(
  mutation: Omit<ShoppingMutation, "id">,
): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const record: ShoppingMutation = {
      ...mutation,
      id: `${mutation.itemId}-${Date.now()}`,
    };
    const req = tx.objectStore(STORE_NAME).add(record);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

async function getAllMutations(): Promise<ShoppingMutation[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const req = tx.objectStore(STORE_NAME).getAll();
    req.onsuccess = () => resolve(req.result as ShoppingMutation[]);
    req.onerror = () => reject(req.error);
  });
}

async function deleteMutation(id: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const req = tx.objectStore(STORE_NAME).delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function drainShoppingQueue(): Promise<void> {
  const mutations = await getAllMutations();

  for (const mutation of mutations) {
    // Fetch current server state to check updated_at for last-write-wins
    const serverResp = await fetch(
      `${API_URL}/api/v1/shopping/${mutation.itemId}`,
      { headers: { Authorization: `Bearer ${mutation.accessToken}` } },
    ).catch(() => null);

    if (serverResp?.ok) {
      const serverItem = (await serverResp.json()) as ShoppingItemRecord;
      // Skip if server is already newer than when we enqueued
      if (serverItem.updated_at > mutation.enqueuedAt) {
        await deleteMutation(mutation.id);
        continue;
      }
    }

    const patchResp = await fetch(
      `${API_URL}/api/v1/shopping/${mutation.itemId}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${mutation.accessToken}`,
        },
        body: JSON.stringify(mutation.payload),
      },
    ).catch(() => null);

    if (patchResp?.ok) {
      await deleteMutation(mutation.id);
    }
    // Leave failed mutations in queue for next drain attempt
  }
}
