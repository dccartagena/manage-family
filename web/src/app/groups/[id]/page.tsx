"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createAuthBrowserClient } from "@/lib/supabase";

interface GroupItem {
  id: string;
  name: string;
  depth: number;
  role: string;
}

interface InviteResponse {
  token: string;
  invite_url: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchAccessToken(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function loadGroups(): Promise<GroupItem[]> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/groups`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to load groups: ${response.status}`);
  return response.json() as Promise<GroupItem[]>;
}

async function generateInvite(groupId: string): Promise<InviteResponse> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/groups/${groupId}/invites`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ expires_at: null, max_uses: null }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error((detail as { detail?: string }).detail ?? `Error ${response.status}`);
  }
  return response.json() as Promise<InviteResponse>;
}

async function leaveGroup(groupId: string): Promise<void> {
  const token = await fetchAccessToken();
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(`${API_URL}/api/v1/groups/${groupId}/membership`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok && response.status !== 204) {
    const detail = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error((detail as { detail?: string }).detail ?? `Error ${response.status}`);
  }
}

export default function GroupDetailPage() {
  const router = useRouter();
  const params = useParams();
  const groupId = params.id as string;

  const [group, setGroup] = useState<GroupItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [inviteUrl, setInviteUrl] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [copied, setCopied] = useState(false);
  const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    loadGroups()
      .then((groups) => {
        const found = groups.find((g) => g.id === groupId) ?? null;
        setGroup(found);
        if (!found) setError("Household not found");
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [groupId]);

  async function handleGenerateInvite() {
    setInviteError("");
    try {
      const invite = await generateInvite(groupId);
      setInviteUrl(invite.invite_url);
      setCopied(false);
    } catch (err: unknown) {
      setInviteError(err instanceof Error ? err.message : "Failed to generate invite");
    }
  }

  async function handleCopyInvite() {
    await navigator.clipboard.writeText(inviteUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleLeave() {
    setLeaving(true);
    try {
      await leaveGroup(groupId);
      router.push("/groups");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to leave group");
      setLeaving(false);
      setShowLeaveConfirm(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-md p-6">
        <p className="text-muted-foreground">Loading…</p>
      </main>
    );
  }

  if (!group) {
    return (
      <main className="mx-auto max-w-md p-6">
        <p role="alert" className="text-sm text-destructive">
          {error || "Household not found"}
        </p>
        <button
          type="button"
          onClick={() => router.push("/groups")}
          className="mt-4 text-sm text-muted-foreground underline"
        >
          Back to households
        </button>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-md space-y-6 p-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.push("/groups")}
          className="text-sm text-muted-foreground hover:text-foreground"
          aria-label="Back to households"
        >
          ← Back
        </button>
        <h1 className="text-xl font-semibold">{group.name}</h1>
        <span
          className={`ml-auto rounded-full px-2 py-0.5 text-xs font-medium ${
            group.role === "owner" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
          }`}
        >
          {group.role}
        </span>
      </div>

      {error && (
        <p role="alert" className="rounded border border-destructive p-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {group.role === "owner" && (
        <section className="space-y-3 rounded-lg border border-border p-4">
          <h2 className="text-sm font-medium">Invite members</h2>
          {inviteError && (
            <p role="alert" className="text-xs text-destructive">
              {inviteError}
            </p>
          )}
          {inviteUrl ? (
            <div className="space-y-2">
              <p className="break-all rounded bg-muted px-3 py-2 font-mono text-xs">{inviteUrl}</p>
              <button
                type="button"
                onClick={handleCopyInvite}
                className="w-full rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-accent"
              >
                {copied ? "Copied!" : "Copy invite link"}
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={handleGenerateInvite}
              className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              Generate Invite Link
            </button>
          )}
        </section>
      )}

      <section>
        {!showLeaveConfirm ? (
          <button
            type="button"
            onClick={() => setShowLeaveConfirm(true)}
            className="w-full rounded-md border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-accent"
          >
            Leave household
          </button>
        ) : (
          <div className="space-y-3 rounded-lg border border-border p-4">
            <p className="text-sm font-medium">Leave this household?</p>
            {group.role === "owner" && (
              <p className="text-xs text-muted-foreground">
                As the owner, leaving may permanently delete this household and all its data if you
                are the only member.
              </p>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleLeave}
                disabled={leaving}
                className="flex-1 rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:opacity-90 disabled:opacity-50"
              >
                {leaving ? "Leaving…" : "Leave"}
              </button>
              <button
                type="button"
                onClick={() => setShowLeaveConfirm(false)}
                className="flex-1 rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-accent"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
