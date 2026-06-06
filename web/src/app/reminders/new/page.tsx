"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createAuthBrowserClient } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchToken(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export default function NewReminderPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [fireAtLocal, setFireAtLocal] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !fireAtLocal) return;

    setSubmitting(true);
    setError(null);

    try {
      const token = await fetchToken();
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

      const response = await fetch(`${API_URL}/api/v1/reminders`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title: title.trim(),
          fire_at_local: fireAtLocal,
          timezone,
        }),
      });

      if (!response.ok) {
        const body = (await response.json()) as { detail?: string };
        throw new Error(body.detail ?? `Request failed: ${response.status}`);
      }

      router.push("/reminders");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      <h1 className="text-xl font-semibold">Add reminder</h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        <section className="space-y-1">
          <label htmlFor="title" className="block text-sm font-medium">
            Title
          </label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Reminder name"
            required
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </section>

        <section className="space-y-1">
          <label htmlFor="fire-at" className="block text-sm font-medium">
            Date and time
          </label>
          <input
            id="fire-at"
            type="datetime-local"
            value={fireAtLocal}
            onChange={(e) => setFireAtLocal(e.target.value)}
            required
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <p className="text-xs text-muted-foreground">
            Time is interpreted in your device&apos;s local timezone.
          </p>
        </section>

        {error && (
          <p role="alert" className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </p>
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
            disabled={submitting || !title.trim() || !fireAtLocal}
            className="flex-1 rounded-md bg-primary py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save reminder"}
          </button>
        </div>
      </form>
    </main>
  );
}
