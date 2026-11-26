"use client";

import { useEffect, useState } from "react";
import { useLive } from "./live";

export type { Link } from "./live";

/** Live state of the camera-junction runtime (/ws), from the shared connection in lib/live.ts. */
export function useEquiflow() {
  const eq = useLive((s) => s.eq);
  return { snapshot: eq.snapshot, events: eq.events, link: eq.link, receivedAt: eq.receivedAt, eventsLoaded: eq.eventsLoaded };
}

/** Re-renders every `ms` so countdowns move smoothly between 2 Hz snapshots. */
export function useTicker(ms = 200) {
  const [, setN] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setN((n) => n + 1), ms);
    return () => clearInterval(id);
  }, [ms]);
}

/** Seconds left in the current stage, extrapolated from the last snapshot. */
export function smoothRemaining(remaining: number | null | undefined, receivedAt: number): number | null {
  if (remaining === null || remaining === undefined) return null;
  const age = (performance.now() - receivedAt) / 1000;
  return Math.max(0, remaining - age);
}
