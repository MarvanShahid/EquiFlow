"use client";

import {
  Bell,
  LogIn,
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Sun,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { NOTIFY, toFeed } from "@/lib/events";
import { clock } from "@/lib/format";
import { useLive } from "@/lib/live";
import { ROLE_LABEL, useSession } from "../session";
import { Badge, LinkBadge, SEVERITY_TONE } from "../ui";
import { Logo } from "./Logo";
import { NAV, navFor } from "./nav";

const COLLAPSE_KEY = "equiflow_sidebar_collapsed";
const THEME_KEY = "equiflow_theme";
const SEEN_KEY = "equiflow_notifications_seen";

function readLS(k: string): string | null {
  try {
    return window.localStorage.getItem(k);
  } catch {
    return null;
  }
}
function writeLS(k: string, v: string) {
  try {
    window.localStorage.setItem(k, v);
  } catch {}
}

export function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  useEffect(() => {
    const read = () => setTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
    read();
    window.addEventListener("equiflow:theme", read);
    return () => window.removeEventListener("equiflow:theme", read);
  }, []);
  const apply = (t: "dark" | "light") => {
    document.documentElement.dataset.theme = t;
    writeLS(THEME_KEY, t);
    window.dispatchEvent(new Event("equiflow:theme"));
  };
  return { theme, setTheme: apply };
}

export default function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname() ?? "/";
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => setCollapsed(readLS(COLLAPSE_KEY) === "1"), []);
  useEffect(() => setMobileOpen(false), [path]);
  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMobileOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileOpen]);

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      writeLS(COLLAPSE_KEY, c ? "0" : "1");
      return !c;
    });
  };

  const current = navFor(path);
  useEffect(() => {
    document.title = current ? `${current.label} · EquiFlow` : "EquiFlow";
  }, [current]);

  return (
    <div className={`app${collapsed ? " is-collapsed" : ""}${mobileOpen ? " is-mobile-open" : ""}`}>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <Sidebar path={path} collapsed={collapsed} onToggle={toggleCollapsed} />
      <div className="scrim" onClick={() => setMobileOpen(false)} aria-hidden="true" />
      <div className="main">
        <Topbar title={current?.label ?? "EquiFlow"} onMenu={() => setMobileOpen(true)} />
        <FailSafeBanner />
        <main id="main" className="content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ sidebar */
function Sidebar({ path, collapsed, onToggle }: { path: string; collapsed: boolean; onToggle: () => void }) {
  const session = useSession();
  const snapshot = useLive((s) => s.eq.snapshot);
  const activeAmb = snapshot?.ambulances.filter((a) => a.status === "active").length ?? 0;
  const latched = snapshot?.intersections.filter((i) => i.output?.flashing).length ?? 0;

  return (
    <aside className="sidebar" aria-label="Main navigation">
      <Link href="/" className="sb-brand" title="EquiFlow overview">
        <Logo />
        <span className="sb-brand-text">
          <strong>EquiFlow</strong>
          <small>Traffic management</small>
        </span>
      </Link>
      <nav className="sb-nav">
        {NAV.map((g) => (
          <div key={g.group} className="sb-group">
            <div className="sb-label">{g.group}</div>
            <ul>
              {g.items.map((n) => {
                const active = n.href === "/" ? path === "/" : path === n.href || path.startsWith(n.href + "/");
                const alert =
                  n.href === "/signals" && latched > 0 ? (
                    <span className="sb-alert">
                      <Badge tone="solid-crit" icon={false}>
                        <span className="sb-alert-text">Fail-safe</span>
                        <span className="sr-only"> on {latched} intersection(s)</span>
                      </Badge>
                    </span>
                  ) : n.href === "/emergency" && activeAmb > 0 ? (
                    <span className="sb-alert">
                      <Badge tone="solid-emg" icon={false}>
                        {activeAmb}
                        <span className="sr-only"> active emergency vehicle(s)</span>
                      </Badge>
                    </span>
                  ) : null;
                return (
                  <li key={n.href}>
                    <Link href={n.href} className="sb-link" aria-current={active ? "page" : undefined} title={collapsed ? n.label : undefined}>
                      <n.icon size={18} aria-hidden="true" />
                      <span className="sb-text">{n.label}</span>
                      {alert}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="sb-foot">
        <div className="sb-user" title={collapsed ? ROLE_LABEL[session.role] : undefined}>
          <span className="avatar" aria-hidden="true">
            <UserRound size={16} />
          </span>
          <span className="sb-user-text">
            <strong>{ROLE_LABEL[session.role]}</strong>
            <span>
              {session.role === "open"
                ? "Authentication disabled"
                : session.role === "anonymous"
                  ? "Read-only"
                  : session.canOperate
                    ? "Can operate controls"
                    : "Read-only"}
            </span>
          </span>
        </div>
        {session.role === "operator" || session.role === "viewer" ? (
          <button type="button" className="btn ghost sm sb-link" onClick={session.signOut} title="Sign out">
            <LogOut size={16} aria-hidden="true" />
            <span className="sb-text">Sign out</span>
          </button>
        ) : session.role === "anonymous" ? (
          <button type="button" className="btn ghost sm sb-link" onClick={session.requestLogin} title="Sign in">
            <LogIn size={16} aria-hidden="true" />
            <span className="sb-text">Sign in</span>
          </button>
        ) : null}
        <button type="button" className="btn ghost sm sb-link sb-collapse" onClick={onToggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-expanded={!collapsed}>
          {collapsed ? <PanelLeftOpen size={16} aria-hidden="true" /> : <PanelLeftClose size={16} aria-hidden="true" />}
          <span className="sb-text">Collapse</span>
        </button>
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ top bar */
function Topbar({ title, onMenu }: { title: string; onMenu: () => void }) {
  const health = useLive((s) => s.health);
  const eqLink = useLive((s) => s.eq.link);
  const sumoLink = useLive((s) => s.sumo.link);
  const mode = useLive((s) => s.eq.snapshot?.mode ?? s.health.data?.mode ?? null);
  const session = useSession();
  const { theme, setTheme } = useTheme();
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const backendTone = health.ok === null ? "warn" : health.ok ? "ok" : "crit";
  const backendWord = health.ok === null ? "Checking" : health.ok ? "Healthy" : "Unreachable";

  return (
    <header className="topbar">
      <button type="button" className="btn ghost icon tb-menu" onClick={onMenu} aria-label="Open navigation">
        <Menu size={18} aria-hidden="true" />
      </button>
      <div className="tb-title">
        <h1>{title}</h1>
      </div>
      <div className="tb-right">
        <div className="tb-status tb-wide" role="group" aria-label="System status">
          <Badge tone={backendTone} dot pulse={health.ok === null} title={health.error ?? health.data?.mode_reason ?? undefined}>
            <span className="badge-label">Backend: </span>
            {backendWord}
          </Badge>
          {health.ok !== false && (
            <>
              <LinkBadge link={eqLink} label="Junction" />
              <LinkBadge link={sumoLink} label="Simulation" />
            </>
          )}
          {mode && (
            <Badge tone="neutral" icon={false} title={health.data?.mode_reason}>
              {mode === "live" ? "Live vision" : "Simulated vision"}
            </Badge>
          )}
        </div>
        <div className="tb-status tb-narrow" role="group" aria-label="System status">
          {(() => {
            const down = health.ok === false ? "Backend offline" : eqLink === "offline" ? "Junction offline" : sumoLink === "offline" ? "Simulation offline" : null;
            const wait = health.ok === null || eqLink === "connecting" || sumoLink === "connecting";
            return (
              <Badge tone={down ? "crit" : wait ? "warn" : "ok"} dot pulse={wait && !down}>
                {down ?? (wait ? "Connecting" : "Connected")}
              </Badge>
            );
          })()}
        </div>
        {now !== null && (
          <time className="tb-clock num" dateTime={new Date(now).toISOString()}>
            {new Date(now).toLocaleDateString([], { day: "2-digit", month: "short" })} {clock(now / 1000)}
          </time>
        )}
        <Notifications />
        <button
          type="button"
          className="btn ghost icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          title={theme === "dark" ? "Light theme" : "Dark theme"}
        >
          {theme === "dark" ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}
        </button>
        {session.role === "anonymous" && (
          <button type="button" className="btn sm primary" onClick={session.requestLogin}>
            <LogIn size={15} aria-hidden="true" /> Sign in
          </button>
        )}
        {(session.role === "operator" || session.role === "viewer") && (
          <span className="tb-role"><Badge tone={session.role === "operator" ? "info" : "neutral"} icon={false} title={session.expiresAt ? `Session ends ${new Date(session.expiresAt).toLocaleTimeString()}` : undefined}>
            {ROLE_LABEL[session.role]}
          </Badge></span>
        )}
      </div>
    </header>
  );
}

function Notifications() {
  const runtime = useLive((s) => s.eq.events);
  const sumo = useLive((s) => s.sumo.events);
  const mode = useLive((s) => s.eq.snapshot?.mode);
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);
  useEffect(() => setSeen(Number(readLS(SEEN_KEY) ?? 0)), []);

  const items = useMemo(() => toFeed(runtime, sumo, mode).filter((f) => NOTIFY.includes(f.d.severity)).slice(0, 30), [runtime, sumo, mode]);
  const unread = items.filter((i) => i.ts > seen).length;

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => wrap.current && !wrap.current.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const markRead = () => {
    const ts = items[0]?.ts ?? Date.now() / 1000;
    setSeen(ts);
    writeLS(SEEN_KEY, String(ts));
  };

  return (
    <div ref={wrap} style={{ position: "relative" }}>
      <button
        type="button"
        className="btn ghost icon notif-btn"
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        aria-controls="notif-panel"
        onClick={() => setOpen((o) => !o)}
      >
        <Bell size={17} aria-hidden="true" />
        {unread > 0 && <span className="notif-count" aria-hidden="true">{unread > 9 ? "9+" : unread}</span>}
      </button>
      {open && (
        <div
          id="notif-panel"
          className="card"
          style={{ position: "absolute", right: 0, top: 44, width: "min(400px, calc(100vw - 24px))", boxShadow: "var(--shadow)", zIndex: 40 }}
        >
          <div className="card-head" style={{ paddingBottom: 10, borderBottom: "1px solid var(--border)" }}>
            <div className="card-head-text">
              <h2 className="card-title">Alerts</h2>
              <p className="card-sub">Critical, warning and emergency events</p>
            </div>
            <div className="card-actions">
              <button type="button" className="btn sm" onClick={markRead} disabled={!unread}>
                Mark all read
              </button>
            </div>
          </div>
          {items.length === 0 ? (
            <p className="muted" style={{ padding: 16 }}>No alerts received in this session.</p>
          ) : (
            <ol className="feed scroll-y" style={{ maxHeight: 360 }}>
              {items.map((f) => (
                <li key={f.key} className={`sev-${f.d.severity}`}>
                  <span className="f-icon" aria-hidden="true">
                    •
                  </span>
                  <div>
                    <div className="f-text">{f.d.text}</div>
                    <div className="f-meta">
                      <Badge tone={SEVERITY_TONE[f.d.severity]}>{f.d.severity === "emg" ? "Emergency" : f.d.severity === "crit" ? "Critical" : "Warning"}</Badge>
                      <Badge icon={false}>{f.origin === "simulation" ? "Simulation" : "Camera junction"}</Badge>
                      {f.ts > seen && <Badge tone="info" icon={false}>New</Badge>}
                    </div>
                  </div>
                  <time>{clock(f.ts)}</time>
                </li>
              ))}
            </ol>
          )}
          <div className="card-foot">
            <Link href="/logs" onClick={() => setOpen(false)}>
              Open system logs
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ global fail-safe warning */
function FailSafeBanner() {
  const snapshot = useLive((s) => s.eq.snapshot);
  const path = usePathname();
  const latched = snapshot?.intersections.filter((i) => i.output?.flashing) ?? [];
  if (!latched.length) return null;
  return (
    <div className="failsafe-banner">
      <div className="banner crit" role="alert">
        <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2">
          <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <div className="banner-text">
          <strong>Fail-safe latched: signals flashing red at {latched.map((i) => i.name || i.id).join(", ")}</strong>
          <p>
            The independent conflict monitor stopped normal operation
            {latched[0].output?.fault ? ` (${latched[0].output.fault.kind}: ${latched[0].output.fault.detail})` : ""}. Commands no longer
            reach the signal heads until an operator resets the output and the backend accepts the reset.
          </p>
        </div>
        {path !== "/signals" && (
          <Link href="/signals" className="btn danger sm">
            Open signal control
          </Link>
        )}
      </div>
    </div>
  );
}
