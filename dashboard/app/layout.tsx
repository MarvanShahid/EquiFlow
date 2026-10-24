import type { Metadata } from "next";
import { Overpass } from "next/font/google";
import "./globals.css";

const overpass = Overpass({ subsets: ["latin"], variable: "--font-overpass", display: "swap" });

export const metadata: Metadata = {
  title: "EquiFlow",
  description: "Ambulance-aware traffic signal control",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={overpass.variable}>
      <body>{children}</body>
    </html>
  );
}
