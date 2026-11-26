"use client";

/* Session state for the UI. The backend is the authority (app/security.py): this only decides what to show
   (sign-in screen, read-only controls) and reacts when the backend says the token is no longer valid. */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  API_URL,
  SESSION_CHANGED_EVENT,
  SESSION_EXPIRED_EVENT,
  apiHeaders,
  clearToken,
  getRole,
  getTokenExpiry,
  getWhoAmI,
  signOut as apiSignOut,
  tokenExpired,
  type WhoAmI,
} from "@/lib/api";
import { restartLive, startLive } from "@/lib/live";
import Login from "./Login";

export type SessionRole = "operator" | "viewer" | "anonymous" | "open";

export interface Session {
  /** null until /api/auth/whoami answered (or failed) */
  auth: WhoAmI | null;
  backendReachable: boolean | null;
  role: SessionRole;
  /** the UI may offer write controls; the backend still checks every request */
  canOperate: boolean;
  expiresAt: number | null;
  expired: boolean;
  signOut: () => void;
  requestLogin: () => void;
}

const Ctx = createContext<Session | null>(null);
export const useSession = () => {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSession outside SessionProvider");
  return s;
};

export const ROLE_LABEL: Record<SessionRole, string> = {
  operator: "Operator",
  viewer: "Viewer",
  anonymous: "Not signed in",
  open: "Open access",
};

export function SessionProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<WhoAmI | null>(null);
  const [reachable, setReachable] = useState<boolean | null>(null);
  const [tokenRole, setTokenRole] = useState<"operator" | "viewer" | "">("");
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [expired, setExpired] = useState(false);
  const [checked, setChecked] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const [mustLogin, setMustLogin] = useState(false);

  const readToken = useCallback(() => {
    setTokenRole(getRole());
    setExpiresAt(getTokenExpiry());
  }, []);

  // ask the backend how it is protected; repeat so a restarted backend with new settings is noticed
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const check = async () => {
      try {
        const who = await getWhoAmI();
        if (!alive) return;
        if (tokenExpired()) {
          clearToken();
          setExpired(true);
        }
        setAuth(who);
        setReachable(true);
        readToken();
        if (who.auth === "enabled" && who.protect_reads) {
          // reads are protected: verify the stored token against a protected endpoint
          const r = await fetch(`${API_URL}/api/config`, { headers: apiHeaders(false), cache: "no-store" });
          if (!alive) return;
          if (r.status === 401) {
            clearToken();
            readToken();
            setMustLogin(true);
          } else setMustLogin(false);
        } else setMustLogin(false);
      } catch {
        if (alive) setReachable(false); // pages show their own offline states
      } finally {
        if (alive) {
          setChecked(true);
          timer = setTimeout(check, 60_000);
        }
      }
    };
    check();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [readToken]);

  // the backend rejected the token, or it ran out
  useEffect(() => {
    const onExpired = () => {
      if (!getRole() && !tokenRole) return;
      clearToken();
      readToken();
      setExpired(true);
      if (auth?.protect_reads) setMustLogin(true);
    };
    const onChanged = () => {
      readToken();
      setExpired(false);
      restartLive();
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    window.addEventListener(SESSION_CHANGED_EVENT, onChanged);
    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
      window.removeEventListener(SESSION_CHANGED_EVENT, onChanged);
    };
  }, [auth, tokenRole, readToken]);

  // local expiry timer
  useEffect(() => {
    if (!expiresAt) return;
    const ms = expiresAt - Date.now();
    const t = setTimeout(() => window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT)), Math.max(0, ms));
    return () => clearTimeout(t);
  }, [expiresAt]);

  // open the shared live connections once we know whether a token is needed
  useEffect(() => {
    if (checked && !mustLogin) startLive();
  }, [checked, mustLogin]);

  const authEnabled = auth?.auth === "enabled";
  const role: SessionRole = !auth || !authEnabled ? "open" : tokenRole || "anonymous";
  const value = useMemo<Session>(
    () => ({
      auth,
      backendReachable: reachable,
      role,
      canOperate: role === "operator" || role === "open",
      expiresAt,
      expired,
      signOut: () => {
        apiSignOut();
        if (auth?.protect_reads) setMustLogin(true);
      },
      requestLogin: () => setLoginOpen(true),
    }),
    [auth, reachable, role, expiresAt, expired],
  );

  if (!checked) {
    return (
      <div className="login-main" style={{ minHeight: "100vh" }} role="status" aria-live="polite">
        <p className="muted">Checking the EquiFlow backend…</p>
      </div>
    );
  }
  if (mustLogin)
    return (
      <Ctx.Provider value={value}>
        <Login expired={expired} required onDone={() => setMustLogin(false)} />
      </Ctx.Provider>
    );
  return (
    <Ctx.Provider value={value}>
      {children}
      {loginOpen && <Login expired={expired} onDone={() => setLoginOpen(false)} onCancel={() => setLoginOpen(false)} />}
    </Ctx.Provider>
  );
}
