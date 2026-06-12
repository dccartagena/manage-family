"use client";

import { useState } from "react";
import { createAuthBrowserClient } from "@/lib/supabase";

type Mode = "signin" | "signup";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

// Return path after auth (e.g. /join/<token> from an invite link). Read from
// window.location instead of useSearchParams to avoid a Suspense boundary;
// only same-origin paths are accepted to prevent open redirects.
function nextPath(): string {
  const next = new URLSearchParams(window.location.search).get("next");
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  function switchMode(next: Mode) {
    setMode(next);
    setError("");
    setInfo("");
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);

    const supabase = createAuthBrowserClient();

    if (mode === "signup") {
      const { data, error: authError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/callback?next=${encodeURIComponent(nextPath())}`,
        },
      });
      if (authError) {
        setError(authError.message);
        setLoading(false);
        return;
      }
      if (!data.session) {
        setInfo("Account created. Check your email to confirm before signing in.");
        setLoading(false);
        return;
      }
      await fetch(`${API_URL}/api/v1/person/sync`, {
        method: "POST",
        headers: { Authorization: `Bearer ${data.session.access_token}` },
      });
      window.location.href = nextPath();
      return;
    }

    const { data, error: authError } = await supabase.auth.signInWithPassword({ email, password });
    if (authError) {
      setError(authError.message);
      setLoading(false);
      return;
    }
    await fetch(`${API_URL}/api/v1/person/sync`, {
      method: "POST",
      headers: { Authorization: `Bearer ${data.session.access_token}` },
    });
    window.location.href = nextPath();
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-6">
      <div className="w-full max-w-sm space-y-2">
        <h1 className="text-2xl font-semibold">
          {mode === "signin" ? "Sign in" : "Create account"}
        </h1>
        <p className="text-sm text-muted-foreground">
          {mode === "signin" ? "Enter your email and password." : "Choose an email and password."}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4">
        {error && (
          <p
            role="alert"
            className="rounded border border-destructive p-2 text-sm text-destructive"
          >
            {error}
          </p>
        )}
        {info && (
          <p
            role="status"
            className="rounded border border-border p-2 text-sm text-muted-foreground"
          >
            {info}
          </p>
        )}

        <div className="space-y-1">
          <label htmlFor="email" className="text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            type="email"
            name="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            placeholder="you@example.com"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="password" className="text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            type="password"
            name="password"
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {loading
            ? mode === "signin"
              ? "Signing in…"
              : "Creating account…"
            : mode === "signin"
              ? "Sign in"
              : "Create account"}
        </button>
      </form>

      <p className="text-sm text-muted-foreground">
        {mode === "signin" ? (
          <>
            No account?{" "}
            <button
              type="button"
              onClick={() => switchMode("signup")}
              className="underline hover:text-foreground"
            >
              Create one
            </button>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <button
              type="button"
              onClick={() => switchMode("signin")}
              className="underline hover:text-foreground"
            >
              Sign in
            </button>
          </>
        )}
      </p>
    </main>
  );
}
