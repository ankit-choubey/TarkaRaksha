import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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
  title: "TarkaRaksha — Agentic Transaction Integrity & Recovery Control Plane",
  description:
    "Payment success doesn't mean transaction success. Deterministic verification, MRDP drift proofs, and bounded autonomous recovery for autonomous commerce.",
  keywords: [
    "TarkaRaksha",
    "Agentic Commerce",
    "Transaction Integrity",
    "MRDP",
    "Razorpay",
    "Autonomous Recovery",
    "Deterministic Verification",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-white text-neutral-900 selection:bg-neutral-900 selection:text-white`}
      >
        {children}
      </body>
    </html>
  );
}
