"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createAuthBrowserClient } from "@/lib/supabase";

interface Group {
  id: string;
  name: string;
}

type RecurrenceOption = "none" | "daily" | "weekly" | "monthly" | "yearly";

const RRULE_MAP: Record<RecurrenceOption, string | null> = {
  none: null,
  daily: "FREQ=DAILY",
  weekly: "FREQ=WEEKLY",
  monthly: "FREQ=MONTHLY",
  yearly: "FREQ=YEARLY",
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchToken(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function fetchGroups(): Promise<Group[]> {
  const token = await fetchToken();
  const response = await fetch(`${API_URL}/api/v1/groups`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to load groups: ${response.status}`);
  return response.json() as Promise<Group[]>;
}

export default function NewEventPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedGroupId = searchParams.get("groupId") ?? "";

  const [groups, setGroups] = useState<Group[]>([]);
  const [groupId, setGroupId] = useState(preselectedGroupId);
  const [title, setTitle] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [recurrence, setRecurrence] = useState<RecurrenceOption>("none");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchGroups()
      .then((gs) => {
        setGroups(gs);
        if (!preselectedGroupId && gs.length > 0) setGroupId(gs[0].id);
      })
      .catch((e: Error) => setError(e.message));
  }, [preselectedGroupId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !startsAt || !groupId) return;

    setSubmitting(true);
    setError(null);

    try {
      const token = await fetchToken();
      const startsAtUtc = new Date(startsAt).toISOString();

      const response = await fetch(`${API_URL}/api/v1/groups/${groupId}/events`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title: title.trim(),
          starts_at: startsAtUtc,
          rrule: RRULE_MAP[recurrence],
        }),
      });

      if (!response.ok) {
        const body = (await response.json()) as { detail?: string };
        throw new Error(body.detail ?? `Request failed: ${response.status}`);
      }

      router.push("/events");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      <h1 className="text-xl font-semibold">Add event</h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        {groups.length > 1 && (
          <section className="space-y-1">
            <label htmlFor="group" className="block text-sm font-medium">
              Group
            </label>
            <select
              id="group"
              value={groupId}
              onChange={(e) => setGroupId(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              required
            >
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </section>
        )}

        <section className="space-y-1">
          <label htmlFor="title" className="block text-sm font-medium">
            Title
          </label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Event name"
            required
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </section>

        <section className="space-y-1">
          <label htmlFor="starts-at" className="block text-sm font-medium">
            Date and time
          </label>
          <input
            id="starts-at"
            type="datetime-local"
            value={startsAt}
            onChange={(e) => setStartsAt(e.target.value)}
            required
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </section>

        <section className="space-y-1">
          <label htmlFor="recurrence" className="block text-sm font-medium">
            Recurrence
          </label>
          <select
            id="recurrence"
            value={recurrence}
            onChange={(e) => setRecurrence(e.target.value as RecurrenceOption)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            <option value="none">Does not repeat</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="yearly">Yearly</option>
          </select>
        </section>

        {error && (
          <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</p>
        )}

        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => router.back()}
            className="flex-1 rounded-md border border-input bg-background py-2 text-sm font-medium"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !title.trim() || !startsAt || !groupId}
            className="flex-1 rounded-md bg-primary py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save event"}
          </button>
        </div>
      </form>
    </main>
  );
}
