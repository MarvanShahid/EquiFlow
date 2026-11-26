/* eslint-disable @next/next/no-img-element */
"use client";

import { CameraOff, Siren, WifiOff } from "lucide-react";
import { useState } from "react";
import { videoUrl } from "@/lib/api";
import type { Approach, Signal } from "@/lib/types";

/** One approach camera: the backend's annotated MJPEG stream (/api/video/{id}/{approach}). Nothing is shown
 *  unless the backend reports the source as running; there is no placeholder "live" picture. */
export default function Camera({ signal, approach, linkUp }: { signal: Signal; approach: Approach; linkUp: boolean }) {
  const src = signal.sources[approach];
  const lamp = signal.output?.flashing ? "red" : signal.lamps[approach];
  const amb = signal.ambulance[approach];
  const simulated = src?.kind === "sim";
  const [broken, setBroken] = useState(false);

  return (
    <figure className={`cam${amb ? " cam-amb" : ""}`}>
      {linkUp && src?.ok && !broken ? (
        <img src={videoUrl(signal.id, approach)} alt={`${approach} approach camera, annotated by the detector`} onError={() => setBroken(true)} />
      ) : (
        <div className="cam-empty" role="status">
          {!linkUp ? <WifiOff size={22} aria-hidden="true" /> : <CameraOff size={22} aria-hidden="true" />}
          <span>{!linkUp ? "Backend offline" : broken ? "Video stream could not be loaded" : src?.error ?? "No video from this source yet"}</span>
          {broken && (
            <button type="button" className="btn sm" onClick={() => setBroken(false)}>
              Retry
            </button>
          )}
        </div>
      )}
      <div className="cam-top">
        {amb && (
          <span className="cam-badge">
            <Siren size={11} aria-hidden="true" style={{ verticalAlign: -1 }} /> Emergency vehicle
          </span>
        )}
      </div>
      <figcaption>
        <span className={`chip chip-${lamp}`} aria-hidden="true" />
        <span className="cam-name">{approach}</span>
        <span className="cam-tag">{lamp}{signal.output?.flashing ? " (flashing)" : ""}</span>
        <span className="cam-tag">· {simulated ? "simulated source" : "camera pipeline"}</span>
        {src?.ok && <span className="cam-fps">{src.fps.toFixed(1)} fps</span>}
      </figcaption>
    </figure>
  );
}
