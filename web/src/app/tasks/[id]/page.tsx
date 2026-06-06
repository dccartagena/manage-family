"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createAuthBrowserClient } from "@/lib/supabase";

interface Task {
  id: string;
  group_id: string;
  title: string;
  rrule: string | null;
  due_at: string | null;
  done: boolean;
  assignee_id: string | null;
}

interface DoneResponse {
  task: Task;
  next_occurrence: Task | null;
}

const RRULE_LABELS: Record<string, string> = {
  "FREQ=DAILY": "Daily",
  "FREQ=WEEKLY": "Weekly",
  "FREQ=MONTHLY": "Monthly",
  "FREQ=YEARLY": "Yearly",
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchAccessToken(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function fetchTask(taskId: string): Promise<Task | null> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  // Tasks are fetched via group endpoint; we store the full object from navigation state.
  // For direct URL access we PATCH with no changes to get the current state via 200 response.
  // Since there is no GET /tasks/{id} endpoint, load via a no-op PATCH.
  const response = await fetch(`${API_URL}/api/v1/tasks/${taskId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({}),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Failed to load task: ${response.status}`);
  return response.json() as Promise<Task>;
}

async function patchTask(
  taskId: string,
  updates: Partial<Pick<Task, "title" | "assignee_id" | "due_at" | "rrule">>
): Promise<Task> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/tasks/${taskId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(updates),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error((detail as { detail?: string }).detail ?? `Error ${response.status}`);
  }
  return response.json() as Promise<Task>;
}

async function markDone(taskId: string): Promise<DoneResponse> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/tasks/${taskId}/done`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error((detail as { detail?: string }).detail ?? `Error ${response.status}`);
  }
  return response.json() as Promise<DoneResponse>;
}

async function undoDone(taskId: string): Promise<Task> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/tasks/${taskId}/done`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error((detail as { detail?: string }).detail ?? `Error ${response.status}`);
  }
  return response.json() as Promise<Task>;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function TaskDetailPage() {
  const router = useRouter();
  const params = useParams();
  const taskId = params.id as string;

  const [task, setTask] = useState<Task | null>(null);
  const [nextOccurrence, setNextOccurrence] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [editingDue, setEditingDue] = useState(false);
  const [dueDraft, setDueDraft] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchTask(taskId)
      .then((loaded) => {
        if (!loaded) {
          setError("Task not found");
        } else {
          setTask(loaded);
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [taskId]);

  async function handleSaveTitle() {
    if (!task || !titleDraft.trim()) return;
    setSaving(true);
    try {
      const updated = await patchTask(taskId, { title: titleDraft.trim() });
      setTask(updated);
      setEditingTitle(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveDue() {
    if (!task) return;
    setSaving(true);
    try {
      const due_at = dueDraft ? new Date(dueDraft).toISOString() : null;
      const updated = await patchTask(taskId, { due_at });
      setTask(updated);
      setEditingDue(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleMarkDone() {
    if (!task) return;
    setSaving(true);
    try {
      const result = await markDone(taskId);
      setTask(result.task);
      setNextOccurrence(result.next_occurrence);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to mark done");
    } finally {
      setSaving(false);
    }
  }

  async function handleUndoDone() {
    if (!task) return;
    setSaving(true);
    try {
      const updated = await undoDone(taskId);
      setTask(updated);
      setNextOccurrence(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to undo");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-md p-6">
        <p className="text-muted-foreground">Loading…</p>
      </main>
    );
  }

  if (!task) {
    return (
      <main className="mx-auto max-w-md space-y-4 p-6">
        <p role="alert" className="text-sm text-destructive">
          {error || "Task not found"}
        </p>
        <button
          type="button"
          onClick={() => router.push("/tasks")}
          className="text-sm text-muted-foreground underline"
        >
          Back to tasks
        </button>
      </main>
    );
  }

  const rruleLabel = task.rrule ? (RRULE_LABELS[task.rrule] ?? task.rrule) : null;

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
        <h1 className="text-xl font-semibold">Task Detail</h1>
        {task.done && (
          <span className="ml-auto rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            Done
          </span>
        )}
      </div>

      {error && (
        <p role="alert" className="rounded border border-destructive p-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {/* Title */}
      <section className="space-y-1">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Title</p>
        {editingTitle ? (
          <div className="flex gap-2">
            <input
              type="text"
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              autoFocus
            />
            <button
              type="button"
              onClick={handleSaveTitle}
              disabled={saving}
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => setEditingTitle(false)}
              className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => {
              setTitleDraft(task.title);
              setEditingTitle(true);
            }}
            className="w-full rounded-md border border-transparent p-1 text-left text-base hover:border-border hover:bg-accent"
          >
            {task.title}
          </button>
        )}
      </section>

      {/* Due date */}
      <section className="space-y-1">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Due</p>
        {editingDue ? (
          <div className="flex gap-2">
            <input
              type="datetime-local"
              value={dueDraft}
              onChange={(e) => setDueDraft(e.target.value)}
              className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              type="button"
              onClick={handleSaveDue}
              disabled={saving}
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => setEditingDue(false)}
              className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => {
              const local = task.due_at
                ? new Date(new Date(task.due_at).getTime() - new Date().getTimezoneOffset() * 60000)
                    .toISOString()
                    .slice(0, 16)
                : "";
              setDueDraft(local);
              setEditingDue(true);
            }}
            className="w-full rounded-md border border-transparent p-1 text-left text-sm hover:border-border hover:bg-accent"
          >
            {task.due_at ? formatDateTime(task.due_at) : "No due date — click to set"}
          </button>
        )}
      </section>

      {/* Recurrence */}
      {rruleLabel && (
        <section className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Recurrence
          </p>
          <p className="text-sm">{rruleLabel}</p>
        </section>
      )}

      {/* Assignee */}
      {task.assignee_id && (
        <section className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Assigned to
          </p>
          <p className="break-all font-mono text-xs text-muted-foreground">{task.assignee_id}</p>
        </section>
      )}

      {/* Next occurrence (shown after marking done for recurring tasks) */}
      {nextOccurrence && (
        <section className="space-y-1 rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Next occurrence created
          </p>
          <p className="text-sm font-medium">{nextOccurrence.title}</p>
          {nextOccurrence.due_at && (
            <p className="text-xs text-muted-foreground">
              Due {formatDateTime(nextOccurrence.due_at)}
            </p>
          )}
        </section>
      )}

      {/* Done / Undo toggle */}
      <div>
        {task.done ? (
          <button
            type="button"
            onClick={handleUndoDone}
            disabled={saving}
            className="w-full rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-accent disabled:opacity-50"
          >
            {saving ? "Undoing…" : "Undo — Mark Incomplete"}
          </button>
        ) : (
          <button
            type="button"
            onClick={handleMarkDone}
            disabled={saving}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Mark Done"}
          </button>
        )}
      </div>
    </main>
  );
}
