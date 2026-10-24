import type { EquiEvent, Signal, Snapshot } from "@/lib/types";
import Camera from "./Camera";
import Plan from "./Plan";
import { ControlsPanel, EventLog, MetricsPanel, StatusPanel } from "./Panels";

/** The 3x3 board: cameras sit on the side of the junction their approach comes from. */
export default function Board({
  snapshot, signal, events, remaining, linkUp,
}: {
  snapshot: Snapshot;
  signal: Signal;
  events: EquiEvent[];
  remaining: number | null;
  linkUp: boolean;
}) {
  return (
    <div className="board">
      <div className="cell c-tl"><StatusPanel signal={signal} remaining={remaining} ambulances={snapshot.ambulances} /></div>
      <div className="cell c-n"><Camera signal={signal} approach="North" linkUp={linkUp} /></div>
      <div className="cell c-tr"><MetricsPanel m={snapshot.metrics} /></div>
      <div className="cell c-w"><Camera signal={signal} approach="West" linkUp={linkUp} /></div>
      <div className="cell c-c"><Plan signal={signal} remaining={remaining} /></div>
      <div className="cell c-e"><Camera signal={signal} approach="East" linkUp={linkUp} /></div>
      <div className="cell c-bl"><ControlsPanel signal={signal} /></div>
      <div className="cell c-s"><Camera signal={signal} approach="South" linkUp={linkUp} /></div>
      <div className="cell c-br"><EventLog events={events} intersectionId={signal.id} /></div>
    </div>
  );
}
