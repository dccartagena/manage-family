"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronRight, User, Home, Monitor, LogOut } from "lucide-react";
import { createAuthBrowserClient } from "@/lib/supabase";

type TextSize = "normal" | "large" | "xlarge";
type Contrast = "normal" | "high";

interface UiPrefs {
  text_size: TextSize;
  contrast: Contrast;
  reduce_motion: boolean;
}

interface PersonData {
  email: string;
  display_name: string;
  ical_secret: string;
}

interface Group {
  id: string;
  name: string;
  role: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchAccessToken(): Promise<string | null> {
  const supabase = createAuthBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function fetchPersonData(): Promise<PersonData | null> {
  const token = await fetchAccessToken();
  const response = await fetch(`${API_URL}/api/v1/person/sync`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) return null;
  return response.json() as Promise<PersonData>;
}

async function fetchGroups(): Promise<Group[]> {
  const token = await fetchAccessToken();
  const response = await fetch(`${API_URL}/api/v1/groups`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) return [];
  return response.json() as Promise<Group[]>;
}

async function patchPrefs(prefs: Partial<UiPrefs>): Promise<UiPrefs> {
  const token = await fetchAccessToken();
  const response = await fetch(`${API_URL}/api/v1/person/prefs`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(prefs),
  });
  if (!response.ok) throw new Error(`Failed to update preferences: ${response.status}`);
  return response.json() as Promise<UiPrefs>;
}

async function patchProfile(displayName: string): Promise<PersonData> {
  const token = await fetchAccessToken();
  const response = await fetch(`${API_URL}/api/v1/person/profile`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ display_name: displayName }),
  });
  if (!response.ok) throw new Error(`Failed to update profile: ${response.status}`);
  return response.json() as Promise<PersonData>;
}

async function createGroup(name: string): Promise<Group> {
  const token = await fetchAccessToken();
  const response = await fetch(`${API_URL}/api/v1/groups`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) throw new Error(`Failed to create household: ${response.status}`);
  return response.json() as Promise<Group>;
}

async function leaveGroup(groupId: string): Promise<void> {
  const token = await fetchAccessToken();
  const response = await fetch(`${API_URL}/api/v1/groups/${groupId}/membership`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Failed to leave household: ${response.status}`);
}

async function generateInvite(groupId: string): Promise<string> {
  const token = await fetchAccessToken();
  const response = await fetch(`${API_URL}/api/v1/groups/${groupId}/invites`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ expires_at: null, max_uses: null }),
  });
  if (!response.ok) throw new Error(`Failed to generate invite: ${response.status}`);
  const data = (await response.json()) as { invite_url: string };
  return data.invite_url;
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

type View = "menu" | "user" | "households" | "system";

export default function SettingsPage() {
  const [view, setView] = useState<View>("menu");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  const [groups, setGroups] = useState<Group[]>([]);
  const [newGroupName, setNewGroupName] = useState("");
  const [creatingGroup, setCreatingGroup] = useState(false);
  const [groupError, setGroupError] = useState<string | null>(null);
  const [confirmLeave, setConfirmLeave] = useState<string | null>(null);
  const [inviteUrls, setInviteUrls] = useState<Record<string, string>>({});
  const [inviteLoading, setInviteLoading] = useState<string | null>(null);
  const [inviteCopied, setInviteCopied] = useState<string | null>(null);

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
      if (stored) setPrefs((prev) => ({ ...prev, ...stored }));
    });

    fetchPersonData().then((person) => {
      if (person) {
        setEmail(person.email);
        setDisplayName(person.display_name);
        setFeedUrl(`${API_URL}/api/v1/ical/${person.ical_secret}`);
      }
    });

    fetchGroups().then(setGroups);
  }, []);

  async function handleSaveProfile() {
    setSavingProfile(true);
    setProfileError(null);
    try {
      const updated = await patchProfile(displayName);
      setDisplayName(updated.display_name);
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleChangePassword(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match");
      return;
    }
    setSavingPassword(true);
    setPasswordError(null);
    setPasswordSuccess(false);
    try {
      const supabase = createAuthBrowserClient();
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) throw new Error(error.message);
      setPasswordSuccess(true);
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : "Failed to update password");
    } finally {
      setSavingPassword(false);
    }
  }

  async function handleCreateGroup(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!newGroupName.trim()) return;
    setCreatingGroup(true);
    setGroupError(null);
    try {
      const group = await createGroup(newGroupName.trim());
      setGroups((prev) => [...prev, group]);
      setNewGroupName("");
    } catch (err) {
      setGroupError(err instanceof Error ? err.message : "Failed to create household");
    } finally {
      setCreatingGroup(false);
    }
  }

  async function handleLeaveGroup(groupId: string) {
    setGroupError(null);
    try {
      await leaveGroup(groupId);
      setGroups((prev) => prev.filter((g) => g.id !== groupId));
      setConfirmLeave(null);
    } catch (err) {
      setGroupError(err instanceof Error ? err.message : "Failed to leave household");
    }
  }

  async function handleGenerateInvite(groupId: string) {
    setInviteLoading(groupId);
    setGroupError(null);
    try {
      const url = await generateInvite(groupId);
      setInviteUrls((prev) => ({ ...prev, [groupId]: url }));
    } catch (err) {
      setGroupError(err instanceof Error ? err.message : "Failed to generate invite");
    } finally {
      setInviteLoading(null);
    }
  }

  async function handleCopyInvite(groupId: string) {
    const url = inviteUrls[groupId];
    if (!url) return;
    await navigator.clipboard.writeText(url);
    setInviteCopied(groupId);
    setTimeout(() => setInviteCopied((prev) => (prev === groupId ? null : prev)), 2000);
  }

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

  async function handleLogout() {
    const supabase = createAuthBrowserClient();
    await supabase.auth.signOut();
    window.location.href = "/login";
  }

  if (view === "menu") {
    return (
      <main className="mx-auto max-w-md space-y-6 p-6 pb-24">
        <h1 className="text-xl font-semibold">Settings</h1>

        <nav aria-label="Settings sections">
          <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
            <li>
              <button
                type="button"
                onClick={() => setView("user")}
                className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-muted/50"
              >
                <User className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">User</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {email || "Profile & password"}
                  </p>
                </div>
                <ChevronRight
                  className="h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
              </button>
            </li>
            <li>
              <button
                type="button"
                onClick={() => setView("households")}
                className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-muted/50"
              >
                <Home className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">Households</p>
                  <p className="text-xs text-muted-foreground">
                    {groups.length === 0
                      ? "No households yet"
                      : `${groups.length} household${groups.length !== 1 ? "s" : ""}`}
                  </p>
                </div>
                <ChevronRight
                  className="h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
              </button>
            </li>
            <li>
              <button
                type="button"
                onClick={() => setView("system")}
                className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-muted/50"
              >
                <Monitor className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">System</p>
                  <p className="text-xs text-muted-foreground">Display & calendar feed</p>
                </div>
                <ChevronRight
                  className="h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
              </button>
            </li>
          </ul>
        </nav>

        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-lg border border-destructive px-4 py-3.5 text-left text-destructive transition-colors hover:bg-destructive hover:text-destructive-foreground"
        >
          <LogOut className="h-5 w-5 shrink-0" aria-hidden="true" />
          <span className="text-sm font-medium">Log out</span>
        </button>
      </main>
    );
  }

  const sectionTitles: Record<Exclude<View, "menu">, string> = {
    user: "User",
    households: "Households",
    system: "System",
  };

  return (
    <main className="mx-auto max-w-md space-y-6 p-6 pb-24">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setView("menu")}
          className="text-sm text-muted-foreground hover:text-foreground"
          aria-label="Back to settings"
        >
          ← Back
        </button>
        <h1 className="text-xl font-semibold">{sectionTitles[view as Exclude<View, "menu">]}</h1>
      </div>

      {view === "user" && (
        <div className="space-y-6">
          <section className="space-y-3">
            <h2 className="text-sm font-semibold">Profile</h2>

            <div className="space-y-1">
              <label className="text-sm font-medium" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                readOnly
                value={email}
                className="w-full rounded-md border border-input bg-muted px-3 py-2 text-sm text-muted-foreground"
              />
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium" htmlFor="display-name">
                Display name
              </label>
              <input
                id="display-name"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="Your name"
              />
            </div>

            {profileError && <p className="text-xs text-destructive">{profileError}</p>}

            <button
              type="button"
              onClick={handleSaveProfile}
              disabled={savingProfile}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {savingProfile ? "Saving…" : "Save profile"}
            </button>
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold">Change password</h2>

            <form onSubmit={handleChangePassword} className="space-y-3">
              <div className="space-y-1">
                <label className="text-sm font-medium" htmlFor="new-password">
                  New password
                </label>
                <input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="••••••••"
                />
              </div>

              <div className="space-y-1">
                <label className="text-sm font-medium" htmlFor="confirm-password">
                  Confirm password
                </label>
                <input
                  id="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="••••••••"
                />
              </div>

              {passwordError && <p className="text-xs text-destructive">{passwordError}</p>}
              {passwordSuccess && (
                <p className="text-xs text-green-600">Password updated successfully.</p>
              )}

              <button
                type="submit"
                disabled={savingPassword}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {savingPassword ? "Updating…" : "Update password"}
              </button>
            </form>
          </section>
        </div>
      )}

      {view === "households" && (
        <section className="space-y-3">
          {groupError && <p className="text-xs text-destructive">{groupError}</p>}

          {groups.length === 0 ? (
            <p className="text-sm text-muted-foreground">No households yet.</p>
          ) : (
            <ul className="space-y-2">
              {groups.map((group) => (
                <li key={group.id} className="space-y-2 rounded-md border border-border px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">{group.name}</p>
                      <p className="text-xs capitalize text-muted-foreground">{group.role}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      {group.role === "owner" && (
                        <button
                          type="button"
                          onClick={() => handleGenerateInvite(group.id)}
                          disabled={inviteLoading === group.id}
                          className="text-xs text-muted-foreground underline hover:text-foreground disabled:opacity-50"
                        >
                          {inviteLoading === group.id ? "…" : "Invite"}
                        </button>
                      )}
                      {confirmLeave === group.id ? (
                        <div className="flex gap-3">
                          <button
                            type="button"
                            onClick={() => setConfirmLeave(null)}
                            className="text-xs text-muted-foreground underline"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={() => handleLeaveGroup(group.id)}
                            className="text-xs text-destructive underline"
                          >
                            Confirm
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmLeave(group.id)}
                          className="text-xs text-muted-foreground underline hover:text-destructive"
                        >
                          Leave
                        </button>
                      )}
                    </div>
                  </div>

                  {inviteUrls[group.id] && (
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        readOnly
                        value={inviteUrls[group.id]}
                        className="flex-1 truncate rounded border border-input bg-muted px-2 py-1 font-mono text-xs"
                        aria-label="Invite link"
                      />
                      <button
                        type="button"
                        onClick={() => handleCopyInvite(group.id)}
                        className="shrink-0 rounded border border-input bg-background px-2 py-1 text-xs font-medium"
                      >
                        {inviteCopied === group.id ? "Copied" : "Copy"}
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          <form onSubmit={handleCreateGroup} className="flex gap-2">
            <input
              type="text"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              placeholder="New household name"
              className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              type="submit"
              disabled={creatingGroup || !newGroupName.trim()}
              className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {creatingGroup ? "…" : "Create"}
            </button>
          </form>
        </section>
      )}

      {view === "system" && (
        <div className="space-y-6">
          <section className="space-y-3">
            <h2 className="text-sm font-semibold">Display</h2>

            <div className="space-y-1">
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
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">High contrast</p>
                <p className="text-xs text-muted-foreground">
                  Increase text and background contrast
                </p>
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
            </div>

            <div className="flex items-center justify-between">
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
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold">Calendar feed</h2>
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
                    className="flex-1 truncate rounded-md border border-input bg-muted px-3 py-2 font-mono text-xs"
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
                    <span className="font-medium">Google Calendar:</span> Settings → Other calendars
                    → From URL → Paste URL
                  </p>
                  <p>
                    <span className="font-medium">Outlook:</span> Add calendar → Subscribe from web
                    → Paste URL
                  </p>
                </div>

                {feedError && <p className="text-xs text-destructive">{feedError}</p>}

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
        </div>
      )}
    </main>
  );
}
