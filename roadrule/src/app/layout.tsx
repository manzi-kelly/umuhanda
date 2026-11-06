import type { Metadata, Viewport } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";

import { SITE } from "@/lib/constants";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-jakarta",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: `${SITE.name} — ${SITE.tagline}`,
    template: `%s | ${SITE.name}`,
  },
  description: SITE.description,
  applicationName: SITE.name,
  keywords: [
    "ikizamini",
    "amategeko y'umuhanda",
    "Rwanda",
    "road rules",
    "online exam",
    "MTN MoMo",
    "Airtel Money",
  ],
  authors: [{ name: SITE.name }],
  openGraph: {
    type: "website",
    locale: "rw_RW",
    siteName: SITE.name,
    title: `${SITE.name} — ${SITE.tagline}`,
    description: SITE.description,
  },
  twitter: {
    card: "summary_large_image",
    title: `${SITE.name} — ${SITE.tagline}`,
    description: SITE.description,
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: "#f6f4ed",
  colorScheme: "light",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="rw" className={`${inter.variable} ${jakarta.variable}`}>
      <body className="flex min-h-dvh flex-col bg-canvas font-sans text-ink antialiased">
        <a
          href="#main-content"
          className="fixed left-4 top-4 z-[100] -translate-y-24 rounded-full bg-brand-950 px-4 py-2 text-sm font-semibold text-white shadow-card transition-transform duration-200 focus:translate-y-0 focus-visible:ring-2 focus-visible:ring-accent-300"
        >
          Simbukira ku bikubiyemo
        </a>
        {children}
      </body>
    </html>
  );
}
