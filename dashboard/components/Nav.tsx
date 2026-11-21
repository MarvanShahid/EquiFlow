"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Live network" },
  { href: "/cameras", label: "Camera feeds" },
  { href: "/results", label: "Results" },
  { href: "/how", label: "How it works" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="nav" aria-label="Main">
      <Link href="/" className="brand">
        <svg viewBox="0 0 32 32" width="26" height="26" aria-hidden="true">
          <rect x="9" y="2" width="14" height="28" rx="5" fill="#11161a" stroke="#3e4953" />
          <circle cx="16" cy="9" r="4" fill="#4aa3ff" />
          <circle cx="16" cy="16" r="4" fill="#3a444e" />
          <circle cx="16" cy="23" r="4" fill="#2fcf8f" />
        </svg>
        EquiFlow
        <small>Ambulance-aware signal control</small>
      </Link>
      <ul>
        {LINKS.map((l) => {
          const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
          return (
            <li key={l.href}>
              <Link href={l.href} aria-current={active ? "page" : undefined}>
                {l.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
