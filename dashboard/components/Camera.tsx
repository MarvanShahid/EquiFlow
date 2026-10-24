/* eslint-disable @next/next/no-img-element */
import { videoUrl } from "@/lib/api";
import type { Approach, Signal } from "@/lib/types";

export default function Camera({ signal, approach, linkUp }: { signal: Signal; approach: Approach; linkUp: boolean }) {
  const src = signal.sources[approach];
  const lamp = signal.lamps[approach];
  const amb = signal.ambulance[approach];
  const simulated = src?.kind === "sim";

  return (
    <figure className={`cam${amb ? " cam-amb" : ""}`}>
      {linkUp && src?.ok ? (
        <img src={videoUrl(signal.id, approach)} alt={`${approach} approach camera`} />
      ) : (
        <div className="cam-empty">
          {!linkUp ? "Backend offline" : (src?.error ?? "No video yet")}
        </div>
      )}
      <figcaption>
        <span className={`chip chip-${lamp}`} aria-label={`${approach} signal is ${lamp}`} />
        <span className="cam-name">{approach}</span>
        {simulated && <span className="cam-tag">simulated</span>}
        {src?.ok && <span className="cam-fps">{src.fps.toFixed(0)} fps</span>}
        {amb && <span className="cam-badge">Ambulance</span>}
      </figcaption>
    </figure>
  );
}
