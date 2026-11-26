"use client";

import { KeyRound, LogIn, LogOut, Monitor, Server, Settings2, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { API_URL, getConfig, type AppConfigInfo } from "@/lib/api";
import { controllerName, dateTime } from "@/lib/format";
import { useLive } from "@/lib/live";
import { ROLE_LABEL, useSession } from "../session";
import { useTheme } from "../shell/AppShell";
import { Badge, Card, KV, LinkBadge, PageHeader, Segmented } from "../ui";

export default function SettingsPage() {
  const session = useSession();
  const health = useLive((s) => s.health);
  const eqLink = useLive((s) => s.eq.link);
  const sumoLink = useLive((s) => s.sumo.link);
  const sumo = useLive((s) => s.sumo.status);
  const { theme, setTheme } = useTheme();
  const [cfg, setCfg] = useState<AppConfigInfo | null>(null);
  const [cfgErr, setCfgErr] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    getConfig().then(setCfg).catch((e) => setCfgErr(e.message));
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const left = session.expiresAt ? Math.max(0, Math.round((session.expiresAt - now) / 1000)) : null;

  return (
    <div className="page">
      <PageHeader
        title="Settings"
        description="Display preferences for this browser, your session, and the backend's connection and configuration. Backend settings are read-only here: they are set in backend/config.yaml and environment variables."
      />
      <div className="grid g-2">
        <Card title="Display" icon={Monitor}>
          <div className="stack">
            <Segmented
              legend="Theme"
              value={theme}
              options={[
                { value: "dark", label: "Dark (control room)" },
                { value: "light", label: "Light" },
              ]}
              onChange={(t) => setTheme(t)}
            />
            <p className="field-hint">Stored in this browser only. The sidebar collapse state is remembered the same way.</p>
          </div>
        </Card>

        <Card title="Session" icon={KeyRound}>
          <div className="stack">
            <KV
              rows={[
                ["Role", <Badge key="r" tone={session.role === "operator" ? "info" : "neutral"} icon={false}>{ROLE_LABEL[session.role]}</Badge>],
                ["Can operate controls", session.canOperate ? "Yes (the backend checks every request)" : "No, read-only"],
                ["Authentication", session.auth ? (session.auth.auth === "enabled" ? "Enabled" : "Disabled (local demo: everything open)") : "Unknown"],
                ["Reads protected", session.auth ? (session.auth.protect_reads ? "Yes, viewer or operator key needed" : "No") : "–"],
                ["Public deployment mode", session.auth ? (session.auth.public ? "Yes" : "No") : "–"],
                ["Session expires", left !== null ? (left > 0 ? `in ${Math.floor(left / 60)} min ${left % 60} s` : "Expired") : session.role === "open" ? "No session needed" : "–"],
              ]}
            />
            <div className="row">
              {(session.role === "operator" || session.role === "viewer") && (
                <button type="button" className="btn sm" onClick={session.signOut}>
                  <LogOut size={14} aria-hidden="true" /> Sign out
                </button>
              )}
              {session.role === "anonymous" && (
                <button type="button" className="btn sm primary" onClick={session.requestLogin}>
                  <LogIn size={14} aria-hidden="true" /> Sign in
                </button>
              )}
            </div>
          </div>
        </Card>

        <Card title="Connection" icon={Server}>
          <KV
            rows={[
              ["Backend URL", <span key="u" className="mono">{API_URL}</span>],
              ["Health", <Badge key="h" tone={health.ok ? "ok" : health.ok === false ? "crit" : "warn"}>{health.ok ? "Healthy" : health.ok === false ? "Unreachable" : "Checking"}</Badge>],
              ["Last health check", health.checkedAt ? dateTime(health.checkedAt / 1000) : "–"],
              ["Junction stream (/ws)", <LinkBadge key="w" link={eqLink} label="Junction" />],
              ["Simulation stream (/ws/sumo)", <LinkBadge key="s" link={sumoLink} label="Simulation" />],
              ["Vision mode", health.data ? (health.data.mode === "live" ? "Live models" : "Simulated") : "–"],
              ["Mode reason", health.data?.mode_reason || "–"],
            ]}
          />
        </Card>

        <Card title="Backend configuration" icon={Settings2} sub="GET /api/config and /api/sumo/status">
          {cfgErr ? (
            <p className="error">Could not read the configuration: {cfgErr}</p>
          ) : (
            <KV
              rows={[
                ["Camera junction controller", cfg ? controllerName(cfg.controller) : "–"],
                ["Intersections", cfg ? cfg.intersections.map((i) => `${i.name} (${i.id})`).join(", ") : "–"],
                ["Approaches", cfg ? cfg.approaches.join(", ") : "–"],
                ["SUMO available", sumo ? (sumo.available ? "Yes" : `No: ${sumo.reason}`) : "–"],
                ["SUMO_HOME", sumo?.sumo_home ? <span key="sh" className="mono">{sumo.sumo_home}</span> : "–"],
              ]}
            />
          )}
        </Card>

        <Card title="Security model" icon={ShieldCheck}>
          <ul className="stack" style={{ fontSize: 13, color: "var(--text-muted)" }}>
            <li>Keys are exchanged once for a short-lived signed token; the key is never stored in the browser.</li>
            <li>The token is kept in this tab&apos;s session storage and sent as a Bearer header (or as ?token= for WebSocket and video URLs).</li>
            <li>Roles are enforced by the backend on every request. Hidden or disabled buttons are only a convenience.</li>
            <li>Failed sign-ins and every write are recorded as events (see System logs) and in the CSV event log.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
