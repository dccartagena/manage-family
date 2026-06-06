"use client";

import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  if (!deferredPrompt || dismissed) return null;

  async function handleInstall() {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted" || outcome === "dismissed") {
      setDeferredPrompt(null);
    }
  }

  return (
    <div role="banner" className="fixed bottom-16 left-0 right-0 z-40 mx-auto max-w-md px-4">
      <div className="flex items-center justify-between rounded-lg border border-border bg-background p-3 shadow-md">
        <span className="text-sm font-medium">Add to Home Screen</span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setDismissed(true)}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            <span>Not now</span>
          </button>
          <button
            type="button"
            onClick={handleInstall}
            className="rounded-md bg-primary px-3 py-1 text-sm font-medium text-primary-foreground"
          >
            <span>Install</span>
          </button>
        </div>
      </div>
    </div>
  );
}
