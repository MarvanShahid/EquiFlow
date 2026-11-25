"use client";

import { useEffect, useState } from "react";
import { API_URL, apiHeaders, clearToken, login } from "@/lib/api";

type State = "checking" | "open" | "need-login";

/** Asks for a key only when the backend protects reads (server.protect_reads / server.public), and again when
 *  the session token has expired. The key is sent once to POST /api/auth/login and never stored. */
export default function LoginGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<State>("checking");
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const who = await fetch(`${API_URL}/api/auth/whoami`).then((r) => r.json());
        if (!who.protect_reads) return alive && setState("open");
        const r = await fetch(`${API_URL}/api/config`, { headers: apiHeaders(false) });
        if (r.status === 401) {
          clearToken();
          if (alive) setState("need-login");
        } else if (alive) setState("open");
      } catch {
        if (alive) setState("open"); // backend unreachable: let the pages show their own offline state
      }
    };
    check();
    const id = setInterval(check, 60_000); // notices an expired token
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (state === "checking") return null;
  if (state === "open") return <>{children}</>;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(key);
      setKey("");
      window.location.reload(); // reconnect the streams with the new token
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main style={{ display: "grid", placeItems: "center", minHeight: "70vh", padding: 24 }}>
      <form onSubmit={submit} style={{ display: "grid", gap: 12, width: "min(360px, 100%)" }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>Sign in to EquiFlow</h1>
        <p style={{ margin: 0, opacity: 0.75, fontSize: 14 }}>
          This deployment needs a viewer or operator key. It is exchanged for a session token and not stored.
        </p>
        <input
          type="password"
          autoComplete="current-password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="Access key"
          aria-label="Access key"
          required
          style={{ padding: "10px 12px", fontSize: 15 }}
        />
        <button type="submit" disabled={busy || !key} style={{ padding: "10px 12px", fontSize: 15 }}>
          {busy ? "Signing in..." : "Sign in"}
        </button>
        {error && (
          <p role="alert" style={{ margin: 0, color: "#c0392b", fontSize: 14 }}>
            {error}
          </p>
        )}
      </form>
    </main>
  );
}
