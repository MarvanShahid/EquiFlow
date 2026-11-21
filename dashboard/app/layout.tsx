import type { Metadata } from "next";
import { Overpass } from "next/font/google";
import Nav from "@/components/Nav";
import "./globals.css";

const overpass = Overpass({ subsets: ["latin"], variable: "--font-overpass", display: "swap" });

export const metadata: Metadata = {
  title: "EquiFlow",
  description: "Ambulance-aware traffic signal control: live network, cameras and results",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={overpass.variable}>
      <body>
        <Nav />
        {children}
      </body>
    </html>
  );
}
