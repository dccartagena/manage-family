import Link from "next/link";

export default function AuthErrorPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-6 text-center">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Link expired or invalid</h1>
        <p className="max-w-sm text-muted-foreground">
          This sign-in link has expired or already been used. Request a new one to continue.
        </p>
      </div>

      <Link
        href="/login"
        className="rounded-md bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        Request a new link
      </Link>
    </main>
  );
}
