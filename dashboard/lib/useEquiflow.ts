"use client";

import { useEffect, useRef, useState } from "react";
import { API_URL, WS_URL } from "./api";
import type { EquiEvent, Snapshot } from "./types";

export type Link = "connecting" | "live" | "offline";
const MAX_EVENTS = 80;

/** Live state from the backend: one WebSocket (snapshots + events) with automatic reconnect. */
export function useEquiflow() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [events, setEvents] = useState<EquiEvent[]>([]);
  const [link, setLink] = useState<Link>("connecting");
  const receivedAt = useRef(0);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let closed = false;
    let attempt = 0;

    fetch(`${API_URL}/api/events?limit=60`)
      .then((r) => (r.ok ? r.json() : []))
      .then((list: EquiEvent[]) => !closed && setEvents(list))
      .catch(() => {});

    const connect = () => {
      setLink("connecting");
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        attempt = 0;
        setLink("live");
      };
      ws.onmessage = (m) => {
        const msg = JSON.parse(m.data);
        if (msg.type === "snapshot") {
          receivedAt.current = performance.now();
          setSnapshot(msg.data as Snapshot);
        } else if (msg.type === "event" && msg.data.type !== "ambulance_position") {
          setEvents((prev) => [msg.data as EquiEvent, ...prev].slice(0, MAX_EVENTS));
        }
      };
      ws.onclose = () => {
        if (closed) return;
        setLink("offline");
        timer = setTimeout(connect, Math.min(8000, 1000 * 2 ** attempt++));
      };
      ws.onerror = () => ws?.close();
    };
    connect();

    return () => {
      closed = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, []);

  return { snapshot, events, link, receivedAt };
}

/** Re-renders every `ms` so countdowns move smoothly between 2 Hz snapshots. */
export function useTicker(ms = 200) {
  const [, setN] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setN((n) => n + 1), ms);
    return () => clearInterval(id);
  }, [ms]);
}
