"use client";

import { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createAuthBrowserClient } from "@/lib/supabase";

type State = "prompt" | "joining" | "expired";

interface AcceptResponse {
  group_id: string;
  group_name: string;
  role: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function acceptInvite(token: string): Promise<AcceptResponse> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  const accessToken = data.session?.access_token;
  if (!accessToken) throw new Error("Not authenticated");

  const response = await fetch(`${API_URL}/api/v1/invites/${token}/accept`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (response.status === 410) {
    const err = new Error("expired") as Error & { code: string };
    err.code = "expired";
    throw err;
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error((detail as { detail?: string }).detail ?? `Error ${response.status}`);
  }
  return response.json() as Promise<AcceptResponse>;
}

export default function JoinPage() {
  const router = useRouter();
  const params = useParams();
  const token = params.token as string;

  const [state, setState] = useState<State>("prompt");
  const [groupName, setGroupName] = useState("");
  const [error, setError] = useState("");

  async function handleJoin() {
    setState("joining");
    try {
      const result = await acceptInvite(token);
      setGroupName(result.group_name);
      router.push("/groups");
    } catch (err: unknown) {
      const e = err as Error & { code?: string };
      if (e.code === "expired") {
        setState("expired");
      } else {
        setError(e.message ?? "Failed to join household");
        setState("prompt");
      }
    }
  }

  if (state === "expired") {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-6">
        <h1 className="text-2xl font-semibold">Invite expired</h1>
        <p className="max-w-sm text-center text-muted-foreground">
          This invite link has expired or has already been used the maximum number of times.
        </p>
        <button
          type="button"
          onClick={() => router.push("/groups")}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Go to households
        </button>
        <p className="text-sm text-muted-foreground">
          Ask the household owner to send a new invite link.
        </p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-6">
      <div className="w-full max-w-sm space-y-2 text-center">
        <h1 className="text-2xl font-semibold">
          {groupName ? `Join ${groupName}` : "Join household"}
        </h1>
        <p className="text-sm text-muted-foreground">
          You have been invited to join a household. Tap the button below to accept.
        </p>
      </div>

      {error && (
        <p role="alert" className="max-w-sm rounded border border-destructive p-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={handleJoin}
        disabled={state === "joining"}
        className="w-full max-w-sm rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
      >
        {state === "joining" ? "Joining…" : "Accept invite"}
      </button>
    </main>
  );
}
