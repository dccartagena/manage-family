"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAuthBrowserClient } from "@/lib/supabase";

interface Reminder {
  id: string;
  title: string;
  fire_at: string;
  delivered: boolean;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchToken(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function fetchReminders(): Promise<Reminder[]> {
  const token = await fetchToken();
  const response = await fetch(`${API_URL}/api/v1/reminders`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to load reminders: ${response.status}`);
  return response.json() as Promise<Reminder[]>;
}

async function deleteReminder(reminderId: string): Promise<void> {
  const token = await fetchToken();
  const response = await fetch(`${API_URL}/api/v1/reminders/${reminderId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to delete reminder: ${response.status}`);
}

function formatFireAt(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function RemindersPage() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReminders()
      .then(setReminders)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(reminderId: string) {
    try {
      await deleteReminder(reminderId);
      setReminders((prev) => prev.filter((r) => r.id !== reminderId));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete reminder");
    }
  }

  const sorted = [...reminders].sort(
    (a, b) => new Date(a.fire_at).getTime() - new Date(b.fire_at).getTime()
  );

  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Reminders</h1>
        <Link
          href="/reminders/new"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          <span>Add reminder</span>
        </Link>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No reminders yet. Add one to get notified via your calendar feed.
        </p>
      ) : (
        <ul className="space-y-3">
          {sorted.map((reminder) => (
            <li
              key={reminder.id}
              className="flex items-start justify-between rounded-lg border border-border p-4"
            >
              <div className="space-y-1">
                <p className="font-medium leading-tight">{reminder.title}</p>
                <p className="text-xs text-muted-foreground">{formatFireAt(reminder.fire_at)}</p>
              </div>
              <div className="ml-3 flex shrink-0 items-center gap-2">
                {reminder.delivered && (
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
                    Delivered
                  </span>
                )}
                <button
                  type="button"
                  aria-label={`Delete reminder "${reminder.title}"`}
                  onClick={() => handleDelete(reminder.id)}
                  className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
                >
                  <span>Delete</span>
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
