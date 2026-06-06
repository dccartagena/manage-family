"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createAuthBrowserClient } from "@/lib/supabase";

interface GroupItem {
  id: string;
  name: string;
  depth: number;
  role: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchAccessToken(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function loadGroups(): Promise<GroupItem[]> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/groups`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to load groups: ${response.status}`);
  return response.json() as Promise<GroupItem[]>;
}

async function createGroup(name: string, parentGroupId: string | null): Promise<{ id: string }> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/groups`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ name, parent_group_id: parentGroupId }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error((detail as { detail?: string }).detail ?? `Error ${response.status}`);
  }
  return response.json() as Promise<{ id: string }>;
}

export default function NewGroupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [parentGroupId, setParentGroupId] = useState<string>("");
  const [parentOptions, setParentOptions] = useState<GroupItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadGroups()
      .then((groups) => setParentOptions(groups.filter((g) => g.depth <= 3)))
      .catch(() => setParentOptions([]));
  }, []);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const group = await createGroup(name.trim(), parentGroupId || null);
      router.push(`/groups/${group.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create household");
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.push("/groups")}
          className="text-sm text-muted-foreground hover:text-foreground"
          aria-label="Back to households"
        >
          ← Back
        </button>
        <h1 className="text-xl font-semibold">Create Household</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <p
            role="alert"
            className="rounded border border-destructive p-2 text-sm text-destructive"
          >
            {error}
          </p>
        )}

        <div className="space-y-1">
          <label htmlFor="name" className="text-sm font-medium">
            Household name
          </label>
          <input
            id="name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Smith Family"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {parentOptions.length > 0 && (
          <div className="space-y-1">
            <label htmlFor="parent" className="text-sm font-medium">
              Parent household <span className="text-muted-foreground">(optional)</span>
            </label>
            <select
              id="parent"
              value={parentGroupId}
              onChange={(e) => setParentGroupId(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">None (root household)</option>
              {parentOptions.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || !name.trim()}
          className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create household"}
        </button>
      </form>
    </main>
  );
}
