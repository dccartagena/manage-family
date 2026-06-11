"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import BarcodeScanner from "@/components/BarcodeScanner";
import { createAuthBrowserClient } from "@/lib/supabase";
import {
  lookupBarcode,
  listCanonicalProducts,
  createCanonicalProduct,
  createInventoryItem,
  type CanonicalProduct,
  type CreateInventoryItemRequest,
} from "@/lib/inventory";
import { EXPIRY_DAYS_BY_CATEGORY } from "@/lib/expiry";

const LOCATIONS = ["fridge", "freezer", "pantry", "other"] as const;
type Location = (typeof LOCATIONS)[number];

interface GroupItem {
  id: string;
  name: string;
  depth: number;
  role: string;
}

type PageState =
  | { stage: "group-select" }
  | { stage: "scanning"; groupId: string }
  | { stage: "looking-up"; groupId: string }
  | { stage: "product-form"; groupId: string; barcode: string; prefill: ProductPrefill }
  | { stage: "manual-form"; groupId: string; barcode: string | null }
  | { stage: "saving" };

interface ProductPrefill {
  name: string;
  location: Location;
  expiryDate: string;
  canonicalProductId: string | null;
  canonicalProducts: CanonicalProduct[];
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

function computeExpiryDate(canonicalProduct: CanonicalProduct | undefined): string {
  const days =
    canonicalProduct?.expiry_days_default ??
    (canonicalProduct ? (EXPIRY_DAYS_BY_CATEGORY[canonicalProduct.category] ?? null) : null);
  if (!days) return "";
  const d = new Date();
  d.setDate(d.getDate() + days);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}-${mm}-${yyyy}`;
}

export default function ScanPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const groupFromUrl = searchParams.get("group");
  const [state, setState] = useState<PageState>(
    groupFromUrl ? { stage: "scanning", groupId: groupFromUrl } : { stage: "group-select" }
  );
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [groupsError, setGroupsError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Form fields
  const [formName, setFormName] = useState("");
  const [formLocation, setFormLocation] = useState<Location>("fridge");
  const [formExpiry, setFormExpiry] = useState("");
  const [formCanonicalId, setFormCanonicalId] = useState<string | null>(null);
  const [canonicalProducts, setCanonicalProducts] = useState<CanonicalProduct[]>([]);
  const [newCanonicalName, setNewCanonicalName] = useState("");

  useEffect(() => {
    fetchGroups()
      .then(setGroups)
      .catch((err: unknown) => {
        setGroupsError(err instanceof Error ? err.message : "Failed to load groups");
      });
  }, []);

  const handleBarcodeDetected = useCallback(
    async (barcode: string) => {
      if (state.stage !== "scanning") return;
      const { groupId } = state;

      setState({ stage: "looking-up", groupId });

      try {
        const token = await fetchAccessToken();
        if (!token) throw new Error("Not authenticated");

        const [lookupResult, cps] = await Promise.all([
          lookupBarcode(barcode),
          listCanonicalProducts(groupId, token),
        ]);

        const matchingCp = lookupResult.canonical_product_id
          ? (cps.find((cp) => cp.id === lookupResult.canonical_product_id) ?? null)
          : null;

        setState({
          stage: "product-form",
          groupId,
          barcode,
          prefill: {
            name: lookupResult.name,
            location: (matchingCp?.usual_location as Location) ?? "fridge",
            expiryDate: computeExpiryDate(matchingCp ?? undefined),
            canonicalProductId: matchingCp?.id ?? null,
            canonicalProducts: cps,
          },
        });
        setFormName(lookupResult.name);
        setFormLocation((matchingCp?.usual_location as Location) ?? "fridge");
        setFormExpiry(computeExpiryDate(matchingCp ?? undefined));
        setFormCanonicalId(matchingCp?.id ?? null);
        setCanonicalProducts(cps);
      } catch (err: unknown) {
        const statusErr = err as Error & { status?: number };
        if (statusErr.status === 404) {
          // Unknown barcode → manual entry
          setState({ stage: "manual-form", groupId, barcode });
          setFormName("");
          setFormLocation("fridge");
          setFormExpiry("");
        } else {
          setFormError(err instanceof Error ? err.message : "Lookup failed");
          setState({ stage: "scanning", groupId });
        }
      }
    },
    [state]
  );

  async function handleSave() {
    if (state.stage !== "product-form" && state.stage !== "manual-form") {
      return;
    }

    setFormError(null);
    const { groupId } = state;
    const barcode = state.stage === "product-form" ? state.barcode : state.barcode;

    try {
      const token = await fetchAccessToken();
      if (!token) throw new Error("Not authenticated");

      let resolvedCanonicalId = formCanonicalId;

      // Create canonical product if user typed a new name
      if (!resolvedCanonicalId && newCanonicalName.trim()) {
        const cp = await createCanonicalProduct(
          groupId,
          {
            name: newCanonicalName.trim(),
            category: "dry_goods",
            is_staple: false,
            usual_location: formLocation,
          },
          token
        );
        resolvedCanonicalId = cp.id;
      }

      if (!resolvedCanonicalId) {
        setFormError("Please select or create a canonical product.");
        return;
      }

      const body: CreateInventoryItemRequest = {
        canonical_product_id: resolvedCanonicalId,
        name: formName.trim(),
        location: formLocation,
      };
      if (barcode) body.barcode = barcode;
      if (formExpiry) body.expiry_date = formExpiry;

      setState({ stage: "saving" });
      await createInventoryItem(groupId, body, token);
      router.push(`/inventory?group=${groupId}`);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Save failed");
      setState(
        state.stage === "product-form"
          ? { stage: "product-form", groupId, barcode: state.barcode, prefill: state.prefill }
          : { stage: "manual-form", groupId, barcode: state.barcode }
      );
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (state.stage === "group-select") {
    return (
      <main className="mx-auto max-w-md p-4">
        <h1 className="mb-4 text-xl font-semibold">Scan Item</h1>
        {groupsError && <p className="mb-3 text-sm text-destructive">{groupsError}</p>}
        <p className="mb-3 text-sm text-muted-foreground">Select a household:</p>
        <ul className="space-y-2">
          {groups.map((g) => (
            <li key={g.id}>
              <button
                className="w-full rounded-lg border border-border px-4 py-3 text-left hover:bg-accent"
                onClick={() => setState({ stage: "scanning", groupId: g.id })}
              >
                {g.name}
              </button>
            </li>
          ))}
        </ul>
      </main>
    );
  }

  if (state.stage === "looking-up") {
    return (
      <main className="mx-auto max-w-md p-4">
        <h1 className="mb-4 text-xl font-semibold">Scan Barcode</h1>
        <p role="status" className="text-center text-muted-foreground">
          Looking up product…
        </p>
      </main>
    );
  }

  if (state.stage === "scanning") {
    return (
      <main className="mx-auto max-w-md p-4">
        <h1 className="mb-4 text-xl font-semibold">Scan Barcode</h1>
        {formError && <p className="mb-3 text-sm text-destructive">{formError}</p>}
        <BarcodeScanner onDetected={handleBarcodeDetected} />
        <button
          className="mt-4 w-full rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground hover:bg-accent"
          onClick={() => setState({ stage: "manual-form", groupId: state.groupId, barcode: null })}
        >
          Enter manually instead
        </button>
      </main>
    );
  }

  if (state.stage === "product-form" || state.stage === "manual-form") {
    const isProductForm = state.stage === "product-form";
    return (
      <main className="mx-auto max-w-md p-4">
        <h1 className="mb-4 text-xl font-semibold">
          {isProductForm ? "Confirm Item" : "Add Item Manually"}
        </h1>
        {formError && (
          <p role="alert" className="mb-3 text-sm text-destructive">
            {formError}
          </p>
        )}

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium">Name</label>
            <input
              className="w-full rounded-lg border border-border px-3 py-2 text-sm"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Location</label>
            <select
              className="w-full rounded-lg border border-border px-3 py-2 text-sm"
              value={formLocation}
              onChange={(e) => setFormLocation(e.target.value as Location)}
            >
              {LOCATIONS.map((l) => (
                <option key={l} value={l}>
                  {l.charAt(0).toUpperCase() + l.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Expiry date (DD-MM-YYYY)</label>
            <input
              className="w-full rounded-lg border border-border px-3 py-2 text-sm"
              placeholder="e.g. 10-06-2026"
              value={formExpiry}
              onChange={(e) => setFormExpiry(e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Canonical product</label>
            <select
              className="w-full rounded-lg border border-border px-3 py-2 text-sm"
              value={formCanonicalId ?? ""}
              onChange={(e) => {
                setFormCanonicalId(e.target.value || null);
                setNewCanonicalName("");
              }}
            >
              <option value="">— Select or create new —</option>
              {canonicalProducts.map((cp) => (
                <option key={cp.id} value={cp.id}>
                  {cp.name}
                </option>
              ))}
            </select>
            {!formCanonicalId && (
              <input
                className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-sm"
                placeholder="New product name…"
                value={newCanonicalName}
                onChange={(e) => setNewCanonicalName(e.target.value)}
              />
            )}
          </div>
        </div>

        <div className="mt-6 flex gap-3">
          <button
            className="flex-1 rounded-lg border border-border px-4 py-2 text-sm hover:bg-accent"
            onClick={() => setState({ stage: "scanning", groupId: state.groupId })}
          >
            Back
          </button>
          <button
            className="flex-1 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
            onClick={handleSave}
          >
            Save
          </button>
        </div>
      </main>
    );
  }

  if (state.stage === "saving") {
    return (
      <main className="mx-auto max-w-md p-4">
        <p className="text-center text-muted-foreground">Saving…</p>
      </main>
    );
  }

  return null;
}
