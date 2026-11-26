import { Card, PageHeader } from "@/components/ui";

export const metadata = { title: "How it works · EquiFlow" };

const STEPS = [
  {
    n: "1",
    title: "A camera on every approach",
    body: "Each road into a junction has its own camera. In the pilot these are recorded Islamabad videos; in the SUMO model every approach has a virtual camera covering the last 120 m before the stop line.",
  },
  {
    n: "2",
    title: "Find and follow every vehicle",
    body: "YOLO26s finds cars, motorcycles, buses and trucks in each frame, and ByteTrack gives each one a stable ID so it can be followed from frame to frame.",
  },
  {
    n: "3",
    title: "Is it an ambulance?",
    body: "Our classifier (cls_v4, trained on public, Pakistani and local ambulance crops) scores every tracked vehicle. A vehicle is confirmed as an ambulance only when 5 of its last 8 frames vote ambulance and the average score is at least 0.65. One noisy frame cannot trigger priority.",
  },
  {
    n: "4",
    title: "Decide the next green",
    body: "Normally the controller serves the busiest movement, gives longer greens to longer queues and guarantees that no approach waits more than 90 s. Two versions: a hand-tuned adaptive rule, and a multi-agent reinforcement learning (MARL) controller, one agent per junction, trained in SUMO to cut waiting while keeping the longest wait short.",
  },
  {
    n: "5",
    title: "Give the ambulance a safe green",
    body: "When an ambulance is confirmed, the current green finishes its 3 s minimum, then yellow (3 s) and all-red (2 s) are always shown before the ambulance's approach turns green. The green is held until the ambulance has gone, plus 4 s. Two ambulances are served first come, first served, and a 60 s fail-safe releases a stuck detection.",
  },
  {
    n: "6",
    title: "Clear the road ahead",
    body: "Once one camera has confirmed an ambulance, the next signals on its route are told it is coming. When it is within about 25 s of a signal, that signal starts clearing for it, before its own camera can see it: a green corridor.",
  },
  {
    n: "7",
    title: "Pay back the waiting",
    body: "Approaches that were held red for the ambulance get extra green afterwards, longest wait first, so the priority is fair to everyone else.",
  },
];

export default function Page() {
  return (
    <div className="page">
      <PageHeader title="How EquiFlow works" description="From a camera frame to a green light for the ambulance, without starving the other roads." />
      <Card title="Pipeline">

      <svg viewBox="0 0 1000 150" className="flow" role="img" aria-label="Pipeline: cameras, vehicle detection and tracking, ambulance classifier and voting, signal controller, signals and dashboard">
        {[
          ["Cameras", "one per approach"],
          ["YOLO26s + ByteTrack", "vehicles with IDs"],
          ["Ambulance classifier", "5-of-8 frame vote"],
          ["Signal controller", "priority + fair recovery"],
          ["Signals + dashboard", "REST, WebSocket, MQTT"],
        ].map(([t, s], i) => (
          <g key={t} transform={`translate(${i * 200}, 0)`}>
            <rect x={6} y={30} width={168} height={90} rx={12} className={i === 2 ? "fbox amb" : i === 3 ? "fbox ctrl" : "fbox"} />
            <text x={90} y={70} textAnchor="middle" className="ft">{t}</text>
            <text x={90} y={94} textAnchor="middle" className="fs">{s}</text>
            {i < 4 && <path d="M178 75 h20 m-7 -6 l7 6 l-7 6" className="farrow" />}
          </g>
        ))}
      </svg>
      </Card>

      <ol className="steps">
        {STEPS.map((s) => (
          <li key={s.n}>
            <span className="stepn">{s.n}</span>
            <div>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <Card title="Where it is tested">
        <div className="prose">
        <p>
          The SUMO model has nine Islamabad junction types: a 4-arm crossing, T- and Y-junctions, 5- and 6-arm chowks, a
          roundabout, a sector grid and a Zero Point style diamond interchange. All drive on the left. The traffic is 62%
          cars, 25% motorcycles, 6% buses and 7% trucks, plus 6 to 14 ambulances an hour. The same controller code that runs
          the camera junction runs every SUMO signal, so the <a href="/simulation">Simulation</a> page shows exactly what would happen
          on the street. The <a href="/reports">Analytics &amp; Reports</a> page compares it with SUMO&apos;s fixed-time and actuated plans.
        </p>
        <p>
          The MARL controller only chooses the next green. Ambulance priority, the green corridor, safety timing and fair
          recovery stay on top of it unchanged, so learning can never make a junction unsafe.
        </p>
        </div>
      </Card>
    </div>
  );
}
