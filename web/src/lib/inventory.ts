const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface CanonicalProduct {
  id: string;
  group_id: string;
  name: string;
  category: string;
  is_staple: boolean;
  usual_location: "fridge" | "freezer" | "pantry" | "other";
  expiry_days_default: number | null;
}

export interface InventoryItem {
  id: string;
  group_id: string;
  canonical_product_id: string;
  canonical_product_name: string;
  barcode: string | null;
  name: string;
  location: "fridge" | "freezer" | "pantry" | "other";
  status: "ok" | "low" | "out";
  expiry_date: string | null;
  added_by: string;
  added_at: string;
}

export interface InventoryItemUpdateResponse extends InventoryItem {
  shopping_item_created: boolean;
  shopping_item_name: string | null;
}

export interface ProductLookupResult {
  barcode: string;
  name: string;
  brand: string | null;
  category: string | null;
  source: "off" | "ah" | "jumbo" | "manual";
  canonical_product_id: string | null;
  canonical_product_name: string | null;
}

export interface LoopCloseResult {
  created: InventoryItem[];
  skipped: string[];
}

export interface CreateCanonicalProductRequest {
  name: string;
  category: string;
  is_staple: boolean;
  usual_location: "fridge" | "freezer" | "pantry" | "other";
  expiry_days_default?: number;
}

export interface UpdateCanonicalProductRequest {
  name?: string;
  category?: string;
  is_staple?: boolean;
  usual_location?: "fridge" | "freezer" | "pantry" | "other";
  expiry_days_default?: number | null;
}

export interface CreateInventoryItemRequest {
  canonical_product_id: string;
  barcode?: string;
  name: string;
  location: "fridge" | "freezer" | "pantry" | "other";
  expiry_date?: string;
}

export interface UpdateInventoryItemRequest {
  status?: "ok" | "low" | "out";
  expiry_date?: string;
}

export interface DeleteInventoryItemRequest {
  removed_reason: "used" | "thrown" | "transferred";
}

export async function lookupBarcode(barcode: string): Promise<ProductLookupResult> {
  const response = await fetch(`${API_URL}/api/v1/inventory/product/${barcode}`);
  if (response.status === 404) {
    const err = new Error("Product not found");
    (err as Error & { status: number }).status = 404;
    throw err;
  }
  if (!response.ok) {
    throw new Error(`Barcode lookup failed: ${response.status}`);
  }
  return response.json() as Promise<ProductLookupResult>;
}

export async function listCanonicalProducts(
  groupId: string,
  token: string,
): Promise<CanonicalProduct[]> {
  const response = await fetch(
    `${API_URL}/api/v1/groups/${groupId}/canonical-products`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!response.ok) {
    throw new Error(`Failed to list canonical products: ${response.status}`);
  }
  return response.json() as Promise<CanonicalProduct[]>;
}

export async function createCanonicalProduct(
  groupId: string,
  body: CreateCanonicalProductRequest,
  token: string,
): Promise<CanonicalProduct> {
  const response = await fetch(
    `${API_URL}/api/v1/groups/${groupId}/canonical-products`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to create canonical product: ${response.status}`);
  }
  return response.json() as Promise<CanonicalProduct>;
}

export async function updateCanonicalProduct(
  canonicalProductId: string,
  body: UpdateCanonicalProductRequest,
  token: string,
): Promise<CanonicalProduct> {
  const response = await fetch(
    `${API_URL}/api/v1/canonical-products/${canonicalProductId}`,
    {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to update canonical product: ${response.status}`);
  }
  return response.json() as Promise<CanonicalProduct>;
}

export async function listInventory(
  groupId: string,
  token: string,
): Promise<InventoryItem[]> {
  const response = await fetch(
    `${API_URL}/api/v1/groups/${groupId}/inventory`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!response.ok) {
    throw new Error(`Failed to list inventory: ${response.status}`);
  }
  return response.json() as Promise<InventoryItem[]>;
}

export async function createInventoryItem(
  groupId: string,
  body: CreateInventoryItemRequest,
  token: string,
): Promise<InventoryItem> {
  const response = await fetch(
    `${API_URL}/api/v1/groups/${groupId}/inventory`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to create inventory item: ${response.status}`);
  }
  return response.json() as Promise<InventoryItem>;
}

export async function updateInventoryItem(
  itemId: string,
  body: UpdateInventoryItemRequest,
  token: string,
): Promise<InventoryItemUpdateResponse> {
  const response = await fetch(`${API_URL}/api/v1/inventory/${itemId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Failed to update inventory item: ${response.status}`);
  }
  return response.json() as Promise<InventoryItemUpdateResponse>;
}

export async function deleteInventoryItem(
  itemId: string,
  body: DeleteInventoryItemRequest,
  token: string,
): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/inventory/${itemId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Failed to delete inventory item: ${response.status}`);
  }
}

export async function fromShoppingItems(
  groupId: string,
  shoppingItemIds: string[],
  token: string,
): Promise<LoopCloseResult> {
  const response = await fetch(
    `${API_URL}/api/v1/groups/${groupId}/inventory/from-shopping`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ shopping_item_ids: shoppingItemIds }),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to loop-close shopping items: ${response.status}`);
  }
  return response.json() as Promise<LoopCloseResult>;
}
