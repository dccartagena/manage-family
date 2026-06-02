import { cookies } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";
import { createAuthServerClient } from "@/lib/supabase";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { searchParams, origin } = request.nextUrl;
  const code = searchParams.get("code");

  if (!code) {
    return NextResponse.redirect(`${origin}/auth/error?reason=missing_code`);
  }

  const cookieStore = cookies();
  const supabase = createAuthServerClient(cookieStore);

  const { data, error } = await supabase.auth.exchangeCodeForSession(code);

  if (error || !data.session) {
    return NextResponse.redirect(`${origin}/auth/error?reason=exchange_failed`);
  }

  const accessToken = data.session.access_token;

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
  const syncResponse = await fetch(`${apiUrl}/api/v1/person/sync`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
  });

  if (!syncResponse.ok) {
    console.error("person/sync failed", syncResponse.status, await syncResponse.text());
  }

  return NextResponse.redirect(`${origin}/dashboard`);
}
