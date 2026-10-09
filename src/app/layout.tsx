import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Tactics Arena",
  description: "A browser auto-battler: build a team, stack synergies, and survive 20 rounds.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      {/* suppressHydrationWarning: browser extensions add attributes to <body> before React loads. */}
      <body className="min-h-full bg-[#0b0d14] text-slate-100" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
