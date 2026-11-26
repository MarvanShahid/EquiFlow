"use client";

import { AlertTriangle, CircleCheck, Info, Loader2, OctagonAlert, ServerOff, Siren, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { API_URL } from "@/lib/api";
import { toFeed, type FeedItem, type Severity } from "@/lib/events";
import { clock, simClock } from "@/lib/format";
import { useLive } from "@/lib/live";
import type { Signal } from "@/lib/types";
import { Badge, Empty, SEVERITY_TONE } from "../ui";

/** Shown when the camera-junction stream has no data yet. */
export function JunctionUnavailable() {
  const link = useLive((s) => s.eq.link);
  const health = useLive((s) => s.health.ok);
  if (link === "offline" || health === false)
    return (
      <Empty icon={ServerOff} title="Backend unreachable">
        No connection to {API_URL}. Start the backend (<code>uvicorn app.main:app --port 8000</code> in <code>backend/</code>, or{" "}
        <code>backend/run_wsl.sh</code> in WSL). This page reconnects automatically.
      </Empty>
    );
  return (
    <Empty icon={Loader2} title="Waiting for the first snapshot">
      Connected to the backend; the camera junction sends its state twice a second.
    </Empty>
  );
}

/** Lets the user pick one of the camera-junction intersections (most deployments have one). */
export function useSelectedSignal(): [Signal | undefined, Signal[], (id: string) => void] {
  const snapshot = useLive((s) => s.eq.snapshot);
  const [picked, setPicked] = useState<string | null>(null);
  const all = snapshot?.intersections ?? [];
  return [all.find((s) => s.id === picked) ?? all[0], all, setPicked];
}

export function SignalPicker({ signals, value, onChange }: { signals: Signal[]; value?: string; onChange: (id: string) => void }) {
  if (signals.length < 2) return null;
  return (
    <div className="chips" role="group" aria-label="Intersection">
      {signals.map((s) => (
        <button key={s.id} type="button" aria-pressed={s.id === value} onClick={() => onChange(s.id)}>
          {s.output?.flashing && <OctagonAlert size={13} aria-label="fail-safe" />}
          {s.name}
        </button>
      ))}
    </div>
  );
}

const SEV_ICON: Record<Severity, LucideIcon> = { crit: OctagonAlert, warn: AlertTriangle, emg: Siren, ok: CircleCheck, info: Info };
const SEV_WORD: Record<Severity, string> = { crit: "Critical", warn: "Warning", emg: "Emergency", ok: "Resolved", info: "Info" };

/** Merged, time-ordered operational events from the junction and the simulation. */
export function ActivityFeed({ limit = 25, filter, maxHeight = 440, origin }: {
  limit?: number;
  filter?: (f: FeedItem) => boolean;
  maxHeight?: number;
  origin?: "junction" | "simulation";
}) {
  const runtime = useLive((s) => s.eq.events);
  const sumo = useLive((s) => s.sumo.events);
  const loaded = useLive((s) => s.eq.eventsLoaded);
  const mode = useLive((s) => s.eq.snapshot?.mode);
  const items = useMemo(() => {
    let f = toFeed(runtime, sumo, mode).filter((x) => x.type !== "api_write" && (!origin || x.origin === origin));
    if (filter) f = f.filter(filter);
    return f.slice(0, limit);
  }, [runtime, sumo, mode, filter, limit, origin]);

  if (!loaded && !items.length) return <Empty compact icon={Loader2} title="Loading events…" />;
  if (!items.length)
    return (
      <Empty compact title="No events yet">
        Signal changes, detections, priority runs and safety alerts appear here as they happen.
      </Empty>
    );
  return (
    <ol className="feed scroll-y" style={{ maxHeight }} aria-label="Recent events, newest first">
      {items.map((f) => (
        <FeedRow key={f.key} f={f} />
      ))}
    </ol>
  );
}

export function FeedRow({ f }: { f: FeedItem }) {
  const Icon = SEV_ICON[f.d.severity];
  return (
    <li className={`sev-${f.d.severity}`}>
      <span className="f-icon">
        <Icon size={16} aria-hidden="true" />
      </span>
      <div style={{ minWidth: 0 }}>
        <div className="f-text">{f.d.text}</div>
        <div className="f-meta">
          <Badge tone={SEVERITY_TONE[f.d.severity]} icon={false}>
            {SEV_WORD[f.d.severity]}
          </Badge>
          <Badge icon={false}>{f.origin === "simulation" ? "Simulation" : "Camera junction"}</Badge>
          {f.d.provenance === "manual" && <Badge tone="warn" icon={false}>Manual / test</Badge>}
          {f.d.provenance === "simulated" && <Badge icon={false}>Simulated detection</Badge>}
          {f.d.provenance === "detected" && <Badge tone="info" icon={false}>Camera detection</Badge>}
        </div>
      </div>
      <time dateTime={new Date(f.ts * 1000).toISOString()} title={f.simTime !== undefined ? `Simulation time ${simClock(f.simTime)}` : undefined}>
        {clock(f.ts)}
        {f.simTime !== undefined && (
          <>
            <br />
            <span className="subtle">sim {simClock(f.simTime)}</span>
          </>
        )}
      </time>
    </li>
  );
}

export function MoreLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="btn sm ghost">
      {children}
    </Link>
  );
}
