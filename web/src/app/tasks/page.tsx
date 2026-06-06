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

interface Task {
  id: string;
  group_id: string;
  title: string;
  rrule: string | null;
  due_at: string | null;
  done: boolean;
  assignee_id: string | null;
}

type FilterTab = "all" | "mine" | "today" | "overdue";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchAccessToken(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function fetchCurrentUserId(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getUser();
  return data.user?.id ?? null;
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

async function fetchTasks(groupId: string): Promise<Task[]> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/groups/${groupId}/tasks`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to load tasks: ${response.status}`);
  return response.json() as Promise<Task[]>;
}

async function markTaskDone(taskId: string): Promise<void> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/tasks/${taskId}/done`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to mark done: ${response.status}`);
}

function isOverdue(task: Task): boolean {
  if (!task.due_at) return false;
  return new Date(task.due_at) < new Date();
}

function isDueToday(task: Task): boolean {
  if (!task.due_at) return false;
  const due = new Date(task.due_at);
  const now = new Date();
  return (
    due.getFullYear() === now.getFullYear() &&
    due.getMonth() === now.getMonth() &&
    due.getDate() === now.getDate()
  );
}

function applyFilter(tasks: Task[], filter: FilterTab, userId: string | null): Task[] {
  switch (filter) {
    case "mine":
      return tasks.filter((t) => t.assignee_id === userId);
    case "today":
      return tasks.filter((t) => isDueToday(t) && !isOverdue(t));
    case "overdue":
      return tasks.filter(isOverdue);
    default:
      return tasks;
  }
}

export default function TasksPage() {
  const router = useRouter();
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string>("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filter, setFilter] = useState<FilterTab>("all");
  const [userId, setUserId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([fetchGroups(), fetchCurrentUserId()])
      .then(([loadedGroups, uid]) => {
        setGroups(loadedGroups);
        setUserId(uid);
        if (loadedGroups.length > 0) {
          setSelectedGroupId(loadedGroups[0].id);
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedGroupId) return;
    setTasksLoading(true);
    fetchTasks(selectedGroupId)
      .then(setTasks)
      .catch((err: Error) => setError(err.message))
      .finally(() => setTasksLoading(false));
  }, [selectedGroupId]);

  async function handleMarkDone(taskId: string) {
    try {
      await markTaskDone(taskId);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to mark done");
    }
  }

  const visibleTasks = applyFilter(tasks, filter, userId);

  if (loading) {
    return (
      <main className="mx-auto max-w-md p-6">
        <p className="text-muted-foreground">Loading…</p>
      </main>
    );
  }

  const filterTabs: { key: FilterTab; label: string }[] = [
    { key: "all", label: "All" },
    { key: "mine", label: "My Tasks" },
    { key: "today", label: "Today" },
    { key: "overdue", label: "Overdue" },
  ];

  return (
    <main className="mx-auto max-w-md space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Tasks</h1>
        {selectedGroupId && (
          <button
            type="button"
            onClick={() => router.push(`/tasks/new?groupId=${selectedGroupId}`)}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Add Task
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="rounded border border-destructive p-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {groups.length > 1 && (
        <select
          value={selectedGroupId}
          onChange={(e) => setSelectedGroupId(e.target.value)}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          aria-label="Select household"
        >
          {groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
      )}

      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No households yet.{" "}
          <button type="button" onClick={() => router.push("/groups/new")} className="underline">
            Create one
          </button>{" "}
          to start tracking tasks.
        </p>
      ) : (
        <>
          <div className="flex gap-1 overflow-x-auto" role="tablist" aria-label="Task filters">
            {filterTabs.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={filter === key}
                onClick={() => setFilter(key)}
                className={`shrink-0 rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                  filter === key
                    ? "bg-primary text-primary-foreground"
                    : "border border-border text-muted-foreground hover:bg-accent"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {tasksLoading ? (
            <p className="text-sm text-muted-foreground">Loading tasks…</p>
          ) : visibleTasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">No tasks here.</p>
          ) : (
            <ul className="space-y-2">
              {visibleTasks.map((task) => {
                const overdue = isOverdue(task);
                return (
                  <li
                    key={task.id}
                    className={`rounded-lg border p-4 ${
                      overdue
                        ? "border-amber-400 bg-amber-50 dark:bg-amber-950/20"
                        : "border-border bg-card"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <button
                        type="button"
                        onClick={() => router.push(`/tasks/${task.id}`)}
                        className="flex-1 text-left"
                      >
                        <p className="font-medium">{task.title}</p>
                        <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                          {task.due_at && (
                            <span>
                              Due{" "}
                              {new Date(task.due_at).toLocaleDateString(undefined, {
                                month: "short",
                                day: "numeric",
                              })}
                            </span>
                          )}
                          {task.rrule && <span>Recurring</span>}
                          {task.assignee_id && <span>Assigned</span>}
                        </div>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleMarkDone(task.id)}
                        aria-label={`Mark "${task.title}" done`}
                        className="shrink-0 rounded-full border border-border p-1.5 hover:bg-accent"
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          aria-hidden="true"
                        >
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                        <span className="sr-only">Done</span>
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </main>
  );
}
