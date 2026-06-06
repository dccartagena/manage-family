"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createAuthBrowserClient } from "@/lib/supabase";

interface GroupItem {
  id: string;
  name: string;
  depth: number;
  role: string;
}

const RRULE_OPTIONS: { label: string; value: string | null }[] = [
  { label: "None (one-off)", value: null },
  { label: "Daily", value: "FREQ=DAILY" },
  { label: "Weekly", value: "FREQ=WEEKLY" },
  { label: "Monthly", value: "FREQ=MONTHLY" },
];

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

async function createTask(
  groupId: string,
  title: string,
  rrule: string | null,
  dueAt: string | null,
  assigneeId: string | null
): Promise<void> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/groups/${groupId}/tasks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      title,
      rrule,
      due_at: dueAt ? new Date(dueAt).toISOString() : null,
      assignee_id: assigneeId || null,
    }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error((detail as { detail?: string }).detail ?? `Error ${response.status}`);
  }
}

export default function NewTaskPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialGroupId = searchParams.get("groupId") ?? "";

  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState(initialGroupId);
  const [title, setTitle] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [rrule, setRrule] = useState<string | null>(null);
  const [assigneeId, setAssigneeId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchGroups()
      .then((loaded) => {
        setGroups(loaded);
        if (!initialGroupId && loaded.length > 0) {
          setSelectedGroupId(loaded[0].id);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [initialGroupId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    if (!selectedGroupId) {
      setError("Select a household");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await createTask(selectedGroupId, title.trim(), rrule, dueAt || null, assigneeId || null);
      router.push("/tasks");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create task");
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.push("/tasks")}
          className="text-sm text-muted-foreground hover:text-foreground"
          aria-label="Back to tasks"
        >
          ← Back
        </button>
        <h1 className="text-xl font-semibold">New Task</h1>
      </div>

      {error && (
        <p role="alert" className="rounded border border-destructive p-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1">
          <label htmlFor="title" className="text-sm font-medium">
            Title <span aria-hidden="true">*</span>
          </label>
          <input
            id="title"
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Take out bins"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {groups.length > 1 && (
          <div className="space-y-1">
            <label htmlFor="group" className="text-sm font-medium">
              Household
            </label>
            <select
              id="group"
              value={selectedGroupId}
              onChange={(e) => setSelectedGroupId(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="space-y-1">
          <label htmlFor="due_at" className="text-sm font-medium">
            Due date & time (optional)
          </label>
          <input
            id="due_at"
            type="datetime-local"
            value={dueAt}
            onChange={(e) => setDueAt(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="rrule" className="text-sm font-medium">
            Recurrence
          </label>
          <select
            id="rrule"
            value={rrule ?? ""}
            onChange={(e) => setRrule(e.target.value || null)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {RRULE_OPTIONS.map((opt) => (
              <option key={opt.label} value={opt.value ?? ""}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1">
          <label htmlFor="assignee" className="text-sm font-medium">
            Assignee person ID (optional)
          </label>
          <input
            id="assignee"
            type="text"
            value={assigneeId}
            onChange={(e) => setAssigneeId(e.target.value)}
            placeholder="UUID of group member"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create Task"}
        </button>
      </form>
    </main>
  );
}
