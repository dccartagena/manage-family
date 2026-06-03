"use client";

import { useCallback, useEffect, useState } from "react";
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

async function fetchIcalSecret(): Promise<string | null> {
  const token = await fetchAccessToken();
  const response = await fetch(`${API_URL}/api/v1/person/sync`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) return null;
  const data = (await response.json()) as { ical_secret: string };
  return data.ical_secret;
}

async function rotateIcalSecret(): Promise<string> {
  const token = await fetchAccessToken();
  const response = await fetch(`${API_URL}/api/v1/ical/rotate`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Rotate failed: ${response.status}`);
  const data = (await response.json()) as { new_feed_url: string };
  return data.new_feed_url;
}

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<UiPrefs>({
    text_size: "normal",
    contrast: "normal",
    reduce_motion: false,
  });
  const [feedUrl, setFeedUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [feedError, setFeedError] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createAuthBrowserClient();
    supabase.auth.getSession().then(({ data }) => {
      const stored = data.session?.user?.user_metadata?.ui_prefs as Partial<UiPrefs> | undefined;
      if (stored) {
        setPrefs((prev) => ({ ...prev, ...stored }));
      }
    });

    fetchIcalSecret().then((secret) => {
      if (secret) {
        setFeedUrl(`${API_URL}/api/v1/ical/${secret}`);
      }
    });
  }, []);

  async function handleChange(update: Partial<UiPrefs>) {
    const next = { ...prefs, ...update };
    setPrefs(next);
    await patchPrefs(update);
  }

  const handleCopy = useCallback(async () => {
    if (!feedUrl) return;
    await navigator.clipboard.writeText(feedUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [feedUrl]);

  async function handleRotate() {
    setRotating(true);
    setFeedError(null);
    try {
      const newUrl = await rotateIcalSecret();
      setFeedUrl(newUrl);
      setConfirmReset(false);
    } catch (err) {
      setFeedError(err instanceof Error ? err.message : "Failed to reset URL");
    } finally {
      setRotating(false);
    }
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

      <section className="space-y-3">
        <h2 className="text-base font-semibold">Calendar feed</h2>
        <p className="text-xs text-muted-foreground">
          Subscribe to your personal iCal feed to see household events in Google Calendar or
          Outlook.
        </p>

        {feedUrl ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={feedUrl}
                className="flex-1 truncate rounded-md border border-input bg-muted px-3 py-2 text-xs font-mono"
                aria-label="iCal feed URL"
              />
              <button
                type="button"
                onClick={handleCopy}
                className="shrink-0 rounded-md border border-input bg-background px-3 py-2 text-xs font-medium"
              >
                {copied ? "Copied" : "Copy"}
              </button>
            </div>

            <div className="space-y-1 text-xs text-muted-foreground">
              <p>
                <span className="font-medium">Google Calendar:</span> Settings → Other calendars →
                From URL → Paste URL
              </p>
              <p>
                <span className="font-medium">Outlook:</span> Add calendar → Subscribe from web →
                Paste URL
              </p>
            </div>

            {feedError && (
              <p className="text-xs text-destructive">{feedError}</p>
            )}

            {!confirmReset ? (
              <button
                type="button"
                onClick={() => setConfirmReset(true)}
                className="text-xs text-muted-foreground underline hover:text-foreground"
              >
                Reset feed URL
              </button>
            ) : (
              <div className="space-y-2 rounded-lg border border-border p-3">
                <p className="text-xs font-medium">
                  Reset your feed URL? Your current URL will stop working immediately.
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setConfirmReset(false)}
                    className="flex-1 rounded-md border border-input bg-background py-1.5 text-xs font-medium"
                  >
                    Keep current
                  </button>
                  <button
                    type="button"
                    onClick={handleRotate}
                    disabled={rotating}
                    className="flex-1 rounded-md bg-destructive py-1.5 text-xs font-medium text-destructive-foreground disabled:opacity-50"
                  >
                    {rotating ? "Resetting…" : "Reset URL"}
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Loading feed URL…</p>
        )}
      </section>
    </main>
  );
}
