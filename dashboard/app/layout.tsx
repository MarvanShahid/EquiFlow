import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import AppShell from "@/components/shell/AppShell";
import { SessionProvider } from "@/components/session";
import { ToastProvider } from "@/components/ui";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono-face", display: "swap" });

export const metadata: Metadata = {
  title: "EquiFlow",
  description: "EquiFlow intelligent traffic management: live junction, signal safety, emergency priority, SUMO simulation and results",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0a111e" };

// Applies the stored theme before the first paint (dark is the default), so there is no flash of the wrong theme.
const THEME_INIT = `try{var t=localStorage.getItem("equiflow_theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;else document.documentElement.dataset.theme="dark"}catch(e){document.documentElement.dataset.theme="dark"}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`} data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body>
        <ToastProvider>
          <SessionProvider>
            <AppShell>{children}</AppShell>
          </SessionProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
