"use client";

import { useState } from "react";
import { useEquiflow, useTicker } from "@/lib/useEquiflow";
import Board from "./Board";

export default function Dashboard() {
  const { snapshot, events, link, receivedAt } = useEquiflow();
  const [picked, setPicked] = useState<string | null>(null);
  useTicker(200);

  const signals = snapshot?.intersections ?? [];
  const signal = signals.find((s) => s.id === picked) ?? signals[0];

  // smooth the countdown between 2 Hz snapshots
  let remaining: number | null = null;
  if (signal && signal.stage_remaining_s !== null) {
    const age = (performance.now() - receivedAt.current) / 1000;
    remaining = Math.max(0, signal.stage_remaining_s - age);
  }

  return (
    <main className="shell">
      <header className="top">
        <h1>EquiFlow</h1>
        {signals.length > 1 && (
          <nav aria-label="Intersections" className="tabs">
            {signals.map((s) => (
              <button key={s.id} aria-pressed={s.id === signal?.id} onClick={() => setPicked(s.id)}>
                {s.name}
              </button>
            ))}
          </nav>
        )}
        <div className="pills">
          {snapshot && (
            <span className="pill" title={snapshot.metrics.mode_reason}>
              {snapshot.mode === "live" ? "Live cameras" : "Simulated cameras"}
            </span>
          )}
          <span className={`pill link-${link}`}>
            {link === "live" ? "Connected" : link === "connecting" ? "Connecting" : "Backend offline"}
          </span>
        </div>
      </header>

      {!signal ? (
        <p className="waiting">
          {link === "offline"
            ? "Can't reach the backend. Start it with “uvicorn app.main:app --port 8000” in the backend folder."
            : "Connecting to the backend…"}
        </p>
      ) : (
        <Board snapshot={snapshot!} signal={signal} events={events} remaining={remaining} linkUp={link === "live"} />
      )}
    </main>
  );
}
