import { createBrowserClient } from "@supabase/ssr";
import { createServerClient, type CookieOptions } from "@supabase/ssr";
import type { ReadonlyRequestCookies } from "next/dist/server/web/spec-extension/adapters/request-cookies";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export function createAuthBrowserClient() {
  return createBrowserClient(supabaseUrl, supabaseAnonKey);
}

export function createAuthServerClient(cookieStore: ReadonlyRequestCookies) {
  return createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      get(name: string) {
        return cookieStore.get(name)?.value;
      },
      set(name: string, value: string, options: CookieOptions) {
        try {
          (cookieStore as unknown as { set: (n: string, v: string, o: CookieOptions) => void }).set(
            name,
            value,
            options
          );
        } catch {
          // Called from a Server Component — session refresh handled by middleware
        }
      },
      remove(name: string, options: CookieOptions) {
        try {
          (cookieStore as unknown as { set: (n: string, v: string, o: CookieOptions) => void }).set(
            name,
            "",
            options
          );
        } catch {
          // Called from a Server Component — session refresh handled by middleware
        }
      },
    },
  });
}
