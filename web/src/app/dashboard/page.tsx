"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAuthBrowserClient } from "@/lib/supabase";

interface DashboardTask {
  id: string;
  title: string;
  group_name: string;
  due_at: string | null;
}

interface DashboardEvent {
  id: string;
  title: string;
  group_name: string;
  starts_at: string;
}

interface DashboardShoppingCount {
  group_id: string;
  group_name: string;
  unchecked_count: number;
}

interface DashboardData {
  overdue_tasks: DashboardTask[];
  today_tasks: DashboardTask[];
  today_events: DashboardEvent[];
  shopping_counts: DashboardShoppingCount[];
  upcoming_events: DashboardEvent[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchDashboard(): Promise<DashboardData> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const response = await fetch(`${API_URL}/api/v1/dashboard`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to load dashboard: ${response.status}`);
  return response.json() as Promise<DashboardData>;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function TaskItem({ task }: { task: DashboardTask }) {
  return (
    <li className="flex items-start justify-between rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/30">
      <div className="space-y-0.5">
        <p className="text-sm font-medium leading-tight">{task.title}</p>
        <p className="text-xs text-muted-foreground">
          {task.group_name}
          {task.due_at ? ` · ${formatDate(task.due_at)}` : ""}
        </p>
      </div>
      <Link
        href={`/tasks/${task.id}`}
        className="ml-3 shrink-0 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
      >
        <span>View</span>
      </Link>
    </li>
  );
}

function EventItem({ event }: { event: DashboardEvent }) {
  return (
    <li className="flex items-start justify-between rounded-lg border border-border p-3">
      <div className="space-y-0.5">
        <p className="text-sm font-medium leading-tight">{event.title}</p>
        <p className="text-xs text-muted-foreground">
          {event.group_name} · {formatDate(event.starts_at)}
        </p>
      </div>
      <Link
        href={`/events/${event.id}`}
        className="ml-3 shrink-0 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
      >
        <span>View</span>
      </Link>
    </li>
  );
}

function SectionHeader({ title }: { title: string }) {
  return <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const isEmpty =
    data &&
    data.overdue_tasks.length === 0 &&
    data.today_tasks.length === 0 &&
    data.today_events.length === 0 &&
    data.shopping_counts.every((sc) => sc.unchecked_count === 0) &&
    data.upcoming_events.length === 0;

  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>

      {error && (
        <p role="alert" className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : isEmpty ? (
        <div className="rounded-lg border border-border p-6 text-center">
          <p className="text-base font-medium">All caught up!</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Nothing needs your attention right now. Enjoy your day.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {data && data.overdue_tasks.length > 0 && (
            <section className="space-y-2" aria-labelledby="overdue-heading">
              <SectionHeader title="Overdue" />
              <ul className="space-y-2" id="overdue-heading">
                {data.overdue_tasks.map((t) => (
                  <TaskItem key={t.id} task={t} />
                ))}
              </ul>
            </section>
          )}

          {data && data.today_tasks.length > 0 && (
            <section className="space-y-2" aria-labelledby="today-tasks-heading">
              <SectionHeader title="Today's Tasks" />
              <ul className="space-y-2" id="today-tasks-heading">
                {data.today_tasks.map((t) => (
                  <TaskItem key={t.id} task={t} />
                ))}
              </ul>
            </section>
          )}

          {data && data.today_events.length > 0 && (
            <section className="space-y-2" aria-labelledby="today-events-heading">
              <SectionHeader title="Today's Events" />
              <ul className="space-y-2" id="today-events-heading">
                {data.today_events.map((e) => (
                  <EventItem key={e.id} event={e} />
                ))}
              </ul>
            </section>
          )}

          {data && data.shopping_counts.some((sc) => sc.unchecked_count > 0) && (
            <section className="space-y-2" aria-labelledby="shopping-heading">
              <SectionHeader title="Shopping" />
              <ul className="space-y-2" id="shopping-heading">
                {data.shopping_counts
                  .filter((sc) => sc.unchecked_count > 0)
                  .map((sc) => (
                    <li key={sc.group_id}>
                      <Link
                        href="/shopping"
                        className="flex items-center justify-between rounded-lg border border-border p-3 hover:bg-muted/50"
                      >
                        <p className="text-sm font-medium">{sc.group_name}</p>
                        <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
                          {sc.unchecked_count} item{sc.unchecked_count !== 1 ? "s" : ""}
                        </span>
                      </Link>
                    </li>
                  ))}
              </ul>
            </section>
          )}

          {data && data.upcoming_events.length > 0 && (
            <section className="space-y-2" aria-labelledby="upcoming-heading">
              <SectionHeader title="Coming Up (7 days)" />
              <ul className="space-y-2" id="upcoming-heading">
                {data.upcoming_events.map((e) => (
                  <EventItem key={e.id} event={e} />
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </main>
  );
}
