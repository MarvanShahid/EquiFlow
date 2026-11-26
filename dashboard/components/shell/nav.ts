import {
  Activity,
  BookOpen,
  BrainCircuit,
  Cctv,
  LayoutDashboard,
  LineChart,
  Network,
  Rows3,
  ScrollText,
  Settings,
  Siren,
  TrafficCone,
  Waypoints,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** short description shown as the page subtitle where useful */
  desc: string;
}

export const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Operations",
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboard, desc: "System-wide status" },
      { href: "/traffic", label: "Live Traffic", icon: Activity, desc: "Camera junction and simulation, live" },
      { href: "/intersections", label: "Intersections", icon: Waypoints, desc: "Every controlled junction" },
      { href: "/signals", label: "Traffic Signals", icon: TrafficCone, desc: "Signal state, safety and operator control" },
      { href: "/lanes", label: "Lane Analytics", icon: Rows3, desc: "Per-lane counts and queues" },
      { href: "/emergency", label: "Emergency Vehicles", icon: Siren, desc: "Detections and priority response" },
    ],
  },
  {
    group: "Control & simulation",
    items: [
      { href: "/marl", label: "MARL Controller", icon: BrainCircuit, desc: "Adaptive controller decisions and training" },
      { href: "/simulation", label: "Simulation (SUMO)", icon: Network, desc: "Run and inspect the SUMO network" },
      { href: "/cameras", label: "Camera Monitoring", icon: Cctv, desc: "Camera sources and processing" },
    ],
  },
  {
    group: "Insights & admin",
    items: [
      { href: "/reports", label: "Analytics & Reports", icon: LineChart, desc: "Controller comparison from SUMO runs" },
      { href: "/logs", label: "System Logs", icon: ScrollText, desc: "Event and audit log" },
      { href: "/settings", label: "Settings", icon: Settings, desc: "Connection, session and display" },
      { href: "/how", label: "How It Works", icon: BookOpen, desc: "Pipeline explained" },
    ],
  },
];

export const ALL_NAV = NAV.flatMap((g) => g.items);

export function navFor(path: string): NavItem | undefined {
  if (path === "/") return ALL_NAV[0];
  return ALL_NAV.filter((n) => n.href !== "/").find((n) => path === n.href || path.startsWith(n.href + "/"));
}
