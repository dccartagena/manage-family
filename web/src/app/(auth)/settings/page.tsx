"use client";

import { useEffect, useState } from "react";
import { createAuthBrowserClient } from "@/lib/supabase";

type TextSize = "normal" | "large" | "xlarge";
type Contrast = "normal" | "high";

interface UiPrefs {
  text_size: TextSize;
  contrast: Contrast;
  reduce_motion: boolean;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchAccessToken(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function patchPrefs(prefs: Partial<UiPrefs>): Promise<UiPrefs> {
  const token = await fetchAccessToken();
  const response = await fetch(`${API_URL}/api/v1/person/prefs`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(prefs),
  });
  if (!response.ok) {
    throw new Error(`Failed to update preferences: ${response.status}`);
  }
  return response.json() as Promise<UiPrefs>;
}

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<UiPrefs>({
    text_size: "normal",
    contrast: "normal",
    reduce_motion: false,
  });

  useEffect(() => {
    const supabase = createAuthBrowserClient();
    supabase.auth.getSession().then(({ data }) => {
      const stored = data.session?.user?.user_metadata?.ui_prefs as Partial<UiPrefs> | undefined;
      if (stored) {
        setPrefs((prev) => ({ ...prev, ...stored }));
      }
    });
  }, []);

  async function handleChange(update: Partial<UiPrefs>) {
    const next = { ...prefs, ...update };
    setPrefs(next);
    await patchPrefs(update);
  }

  return (
    <main className="mx-auto max-w-md space-y-8 p-6">
      <h1 className="text-xl font-semibold">Display settings</h1>

      <section className="space-y-3">
        <label className="block text-sm font-medium" htmlFor="text-size">
          Text size
        </label>
        <select
          id="text-size"
          value={prefs.text_size}
          onChange={(e) => handleChange({ text_size: e.target.value as TextSize })}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="normal">Normal</option>
          <option value="large">Large</option>
          <option value="xlarge">Extra large</option>
        </select>
      </section>

      <section className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">High contrast</p>
          <p className="text-xs text-muted-foreground">Increase text and background contrast</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={prefs.contrast === "high"}
          onClick={() =>
            handleChange({ contrast: prefs.contrast === "high" ? "normal" : "high" })
          }
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            prefs.contrast === "high" ? "bg-primary" : "bg-muted"
          }`}
        >
          <span className="sr-only">Toggle high contrast</span>
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              prefs.contrast === "high" ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </section>

      <section className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">Reduce motion</p>
          <p className="text-xs text-muted-foreground">Minimise animations and transitions</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={prefs.reduce_motion}
          onClick={() => handleChange({ reduce_motion: !prefs.reduce_motion })}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            prefs.reduce_motion ? "bg-primary" : "bg-muted"
          }`}
        >
          <span className="sr-only">Toggle reduce motion</span>
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              prefs.reduce_motion ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </section>
    </main>
  );
}
