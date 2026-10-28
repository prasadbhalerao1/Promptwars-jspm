import type { Metadata } from "next";
import { Inter, IBM_Plex_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/components/AuthProvider";
import { CurrentUserProvider } from "@/components/CurrentUserProvider";
import { SiteHeader } from "@/components/common/SiteHeader";
import "./globals.css";

// Inter for UI, IBM Plex Mono for evidence IDs and score values. Two faces, no third.
// Inter specifically because it enables tabular figures by default (IBM Plex Sans does
// not) — this product renders toFixed() in ~30 places and those columns must align and
// must not jitter as values update. See DESIGN.md §3.
const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "TRACE - Verified Talent Intelligence",
  description:
    "Verified talent identity, AI-driven matching, and fraud-resistant hiring.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${mono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      {/* Colours come from the token layer. This previously hardcoded
 `bg-card text-foreground`, which overrode every token below it. */}
      <body className="flex min-h-full flex-col" suppressHydrationWarning>
        <AuthProvider>
          {/* CurrentUserProvider wraps the header too: it reads useCurrentUser, which
 throws outside the provider. */}
          <CurrentUserProvider>
            <SiteHeader />
            <div className="flex flex-1 flex-col">{children}</div>
          </CurrentUserProvider>
          <Toaster />
        </AuthProvider>
      </body>
    </html>
  );
}
