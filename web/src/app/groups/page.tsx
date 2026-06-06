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

async function fetchGroups(): Promise<GroupItem[]> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("Not authenticated");

  const response = await fetch(`${API_URL}/api/v1/groups`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to load groups: ${response.status}`);
  return response.json() as Promise<GroupItem[]>;
}

export default function GroupsPage() {
  const router = useRouter();
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchGroups()
      .then(setGroups)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <main className="mx-auto max-w-md p-6">
        <p className="text-muted-foreground">Loading households…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Households</h1>
        <button
          type="button"
          onClick={() => router.push("/groups/new")}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Create Household
        </button>
      </div>

      {error && (
        <p role="alert" className="rounded border border-destructive p-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No households yet. Create one to get started.
        </p>
      ) : (
        <ul className="space-y-2">
          {groups.map((group) => (
            <li key={group.id}>
              <button
                type="button"
                onClick={() => router.push(`/groups/${group.id}`)}
                className="flex w-full items-center justify-between rounded-lg border border-border bg-card p-4 text-left hover:bg-accent"
              >
                <div className="space-y-1">
                  <p className="font-medium">{group.name}</p>
                  {group.depth > 0 && (
                    <p className="text-xs text-muted-foreground">Level {group.depth}</p>
                  )}
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    group.role === "owner"
                      ? "bg-primary/10 text-primary"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {group.role}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
