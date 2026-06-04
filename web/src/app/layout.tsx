import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { cookies } from "next/headers";
import Script from "next/script";
import "./globals.css";
import { BottomNav } from "@/components/BottomNav";
import { InstallPrompt } from "@/components/InstallPrompt";
import { createAuthServerClient } from "@/lib/supabase";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Household Manager",
  description: "Private household coordination",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Household",
  },
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const cookieStore = cookies();
  const supabase = createAuthServerClient(cookieStore);
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const uiPrefs =
    (user as { user_metadata?: { ui_prefs?: Record<string, string> } } | null)
      ?.user_metadata?.ui_prefs ?? {};

  const textSize = uiPrefs["text_size"] ?? "normal";
  const contrast = uiPrefs["contrast"] === "high";
  const reduceMotion = uiPrefs["reduce_motion"] === "true";

  const rootClasses = [
    inter.className,
    contrast ? "contrast-high" : "",
    reduceMotion ? "reduce-motion" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const fontScaleVar =
    textSize === "xlarge" ? "1.25rem" : textSize === "large" ? "1.125rem" : "1rem";

  return (
    <html lang="en" className={rootClasses} style={{ fontSize: fontScaleVar }}>
      <body>
        <main className="pb-16">{children}</main>
        {user && <BottomNav />}
        {user && <InstallPrompt />}
        <Script id="sw-register" strategy="afterInteractive">
          {`
            if ('serviceWorker' in navigator) {
              navigator.serviceWorker.register('/sw.js').catch(console.error);
            }
          `}
        </Script>
      </body>
    </html>
  );
}
