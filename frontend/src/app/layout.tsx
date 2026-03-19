import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { RuntimeChunkGuard } from "@/components/shared/runtime-chunk-guard";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ChainIQ Sourcing Decision Cockpit",
  description:
    "Premium internal workspace for governed sourcing decisions, supplier comparison, escalation handling, and audit traceability.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full`}
    >
      <body
        suppressHydrationWarning
        className="h-full bg-background text-foreground"
      >
        <RuntimeChunkGuard />
        <TooltipProvider>{children}</TooltipProvider>
      </body>
    </html>
  );
}
