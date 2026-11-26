export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg className="logo" viewBox="0 0 32 32" width={size} height={size} aria-hidden="true">
      <rect x="1" y="1" width="30" height="30" rx="8" fill="#142036" stroke="#2e4166" />
      <rect x="11" y="5" width="10" height="22" rx="4" fill="#070b13" />
      <circle cx="16" cy="10" r="2.6" fill="#ef4444" />
      <circle cx="16" cy="16" r="2.6" fill="#f5b50b" opacity="0.35" />
      <circle cx="16" cy="22" r="2.6" fill="#22c55e" />
    </svg>
  );
}
