"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { createAuthBrowserClient } from "@/lib/supabase";

interface Event {
  id: string;
  group_id: string;
  title: string;
  starts_at: string;
  rrule: string | null;
}

interface Group {
  id: string;
  role: string;
}

const RRULE_LABELS: Record<string, string> = {
  "FREQ=DAILY": "Repeats daily",
  "FREQ=WEEKLY": "Repeats weekly",
  "FREQ=MONTHLY": "Repeats monthly",
  "FREQ=YEARLY": "Repeats yearly",
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchToken(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "full",
    timeStyle: "short",
  });
}

export default function EventDetailPage() {
  const params = useParams();
  const router = useRouter();
  const eventId = params.id as string;

  const [event, setEvent] = useState<Event | null>(null);
  const [isMember, setIsMember] = useState(false);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const token = await fetchToken();
      const headers = { Authorization: `Bearer ${token}` };

      const groupsResp = await fetch(`${API_URL}/api/v1/groups`, { headers });
      const groups: Group[] = groupsResp.ok
        ? ((await groupsResp.json()) as Group[])
        : [];

      const groupIds = groups.map((g) => g.id);

      for (const groupId of groupIds) {
        const eventsResp = await fetch(`${API_URL}/api/v1/groups/${groupId}/events`, { headers });
        if (!eventsResp.ok) continue;
        const events: Event[] = (await eventsResp.json()) as Event[];
        const found = events.find((e) => e.id === eventId);
        if (found) {
          setEvent(found);
          setIsMember(true);
          break;
        }
      }

      setLoading(false);
    }

    load().catch((e: Error) => {
      setError(e.message);
      setLoading(false);
    });
  }, [eventId]);

  async function handleDelete() {
    if (!event) return;
    setDeleting(true);
    setError(null);

    try {
      const token = await fetchToken();
      const response = await fetch(`${API_URL}/api/v1/events/${event.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.status === 403) {
        throw new Error("You are not a member of the group that owns this event.");
      }
      if (!response.ok) {
        throw new Error(`Delete failed: ${response.status}`);
      }

      router.push("/events");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-md p-6">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </main>
    );
  }

  if (!event) {
    return (
      <main className="mx-auto max-w-md p-6">
        <p className="text-sm text-muted-foreground">Event not found.</p>
      </main>
    );
  }

  const rruleLabel = event.rrule ? (RRULE_LABELS[event.rrule] ?? event.rrule) : null;

  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      <button
        type="button"
        onClick={() => router.back()}
        className="text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back
      </button>

      <div className="space-y-4">
        <h1 className="text-xl font-semibold">{event.title}</h1>

        <dl className="space-y-3">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Date and time
            </dt>
            <dd className="mt-1 text-sm">{formatDate(event.starts_at)}</dd>
          </div>

          {rruleLabel && (
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Recurrence
              </dt>
              <dd className="mt-1 text-sm">{rruleLabel}</dd>
            </div>
          )}
        </dl>
      </div>

      {error && (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</p>
      )}

      {isMember && !confirmDelete && (
        <button
          type="button"
          onClick={() => setConfirmDelete(true)}
          className="w-full rounded-md border border-input bg-background py-2 text-sm font-medium text-destructive"
        >
          Delete event
        </button>
      )}

      {confirmDelete && (
        <div className="space-y-3 rounded-lg border border-border p-4">
          <p className="text-sm font-medium">Delete this event?</p>
          <p className="text-xs text-muted-foreground">This action cannot be undone.</p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setConfirmDelete(false)}
              className="flex-1 rounded-md border border-input bg-background py-2 text-sm font-medium"
            >
              Keep event
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="flex-1 rounded-md bg-destructive py-2 text-sm font-medium text-destructive-foreground disabled:opacity-50"
            >
              {deleting ? "Deleting…" : "Confirm delete"}
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
