"use client";

import { Eye, EyeOff, KeyRound, Loader2, ShieldCheck, TrafficCone, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { API_URL, login } from "@/lib/api";
import { InlineMsg } from "./ui";
import { Logo } from "./shell/Logo";

/** Sign-in screen. The key is sent once to POST /api/auth/login and exchanged for a short-lived session token;
 *  the key itself is never stored. Which role you get (operator or viewer) is decided by the backend from the key. */
export default function Login({ required, expired, onDone, onCancel }: {
  required?: boolean;
  expired?: boolean;
  onDone: () => void;
  onCancel?: () => void;
}) {
  const [key, setKey] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    input.current?.focus();
    if (!onCancel) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!key.trim()) {
      setError("Enter your access key.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const r = await login(key.trim());
      setKey("");
      setDone(r.role === "operator" ? "Signed in as Operator" : r.role === "viewer" ? "Signed in as Viewer" : "Signed in");
      setTimeout(onDone, 350);
    } catch (err) {
      setError((err as Error).message);
      input.current?.focus();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="login"
      role={required ? undefined : "dialog"}
      aria-modal={required ? undefined : true}
      aria-labelledby="login-title"
      style={required ? undefined : { position: "fixed", inset: 0, zIndex: 80, overflow: "auto" }}
    >
      <aside className="login-aside">
        <div>
          <div className="row" style={{ gap: 10 }}>
            <Logo />
            <strong style={{ fontSize: 16 }}>EquiFlow</strong>
          </div>
          <h1>Intelligent traffic signal control</h1>
          <p>
            Camera-based vehicle detection, adaptive and MARL signal control, and safe emergency-vehicle priority behind an
            independent conflict monitor.
          </p>
        </div>
        <div className="login-roles" aria-label="Roles">
          <div className="login-role">
            <span className="kpi-icon" aria-hidden="true">
              <ShieldCheck size={16} />
            </span>
            <div>
              <strong>Operator key</strong>
              <span>Monitor everything, request or cancel test priority, reset a latched signal output, control the simulation.</span>
            </div>
          </div>
          <div className="login-role">
            <span className="kpi-icon" aria-hidden="true">
              <TrafficCone size={16} />
            </span>
            <div>
              <strong>Viewer key</strong>
              <span>Read-only: dashboards, live feeds, analytics and logs. Controls are shown but locked.</span>
            </div>
          </div>
        </div>
      </aside>
      <main className="login-main">
        <form className="login-form" onSubmit={submit} noValidate>
          <div className="row-between">
            <h2 id="login-title">Sign in</h2>
            {onCancel && (
              <button type="button" className="btn ghost icon" aria-label="Close sign-in" onClick={onCancel}>
                <X size={16} aria-hidden="true" />
              </button>
            )}
          </div>
          {expired && <InlineMsg tone="warn">Your session expired. Sign in again to continue.</InlineMsg>}
          <p>
            Enter the operator or viewer key for this deployment. Your role is set by the backend from the key. The key is
            exchanged for a session token and is not stored.
          </p>
          <div className="field">
            <label htmlFor="login-key">Access key</label>
            <div style={{ position: "relative" }}>
              <input
                id="login-key"
                ref={input}
                className="input"
                type={show ? "text" : "password"}
                autoComplete="current-password"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                aria-invalid={!!error}
                aria-describedby={error ? "login-error" : undefined}
                style={{ paddingRight: 44 }}
              />
              <button
                type="button"
                className="btn ghost icon sm"
                style={{ position: "absolute", right: 3, top: 3 }}
                onClick={() => setShow((s) => !s)}
                aria-label={show ? "Hide key" : "Show key"}
                aria-pressed={show}
              >
                {show ? <EyeOff size={15} aria-hidden="true" /> : <Eye size={15} aria-hidden="true" />}
              </button>
            </div>
          </div>
          {error && (
            <p id="login-error" className="inline-msg crit" role="alert">
              {error}
            </p>
          )}
          {done && <InlineMsg tone="ok">{done}</InlineMsg>}
          <button type="submit" className="btn primary block" disabled={busy}>
            {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <KeyRound size={16} aria-hidden="true" />}
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <p className="subtle" style={{ fontSize: 12 }}>
            Backend: <span className="mono">{API_URL}</span>
          </p>
        </form>
      </main>
    </div>
  );
}
