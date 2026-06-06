"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAuthBrowserClient } from "@/lib/supabase";

interface Group {
  id: string;
  name: string;
  depth: number;
  role: string;
}

interface Event {
  id: string;
  group_id: string;
  title: string;
  starts_at: string;
  rrule: string | null;
}

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

async function fetchEvents(groupId: string): Promise<Event[]> {
  const token = await fetchToken();
  const response = await fetch(`${API_URL}/api/v1/groups/${groupId}/events`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to load events: ${response.status}`);
  return response.json() as Promise<Event[]>;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function EventsPage() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string>("");
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchGroups()
      .then((gs) => {
        setGroups(gs);
        if (gs.length > 0) setSelectedGroupId(gs[0].id);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedGroupId) return;
    setLoading(true);
    fetchEvents(selectedGroupId)
      .then(setEvents)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedGroupId]);

  const sorted = [...events].sort(
    (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
  );

  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Events</h1>
        {selectedGroupId && (
          <Link
            href={`/events/new?groupId=${selectedGroupId}`}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            <span>Add event</span>
          </Link>
        )}
      </div>

      {groups.length > 1 && (
        <section>
          <label htmlFor="group-select" className="sr-only">
            Select group
          </label>
          <select
            id="group-select"
            value={selectedGroupId}
            onChange={(e) => setSelectedGroupId(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </section>
      )}

      {error && (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</p>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground">No events yet. Add one to get started.</p>
      ) : (
        <ul className="space-y-3">
          {sorted.map((event) => (
            <li key={event.id}>
              <Link
                href={`/events/${event.id}`}
                className="flex items-start justify-between rounded-lg border border-border p-4 hover:bg-muted/50"
              >
                <div className="space-y-1">
                  <p className="font-medium leading-tight">{event.title}</p>
                  <p className="text-xs text-muted-foreground">{formatDate(event.starts_at)}</p>
                </div>
                {event.rrule && (
                  <span className="ml-3 shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
                    Recurring
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
