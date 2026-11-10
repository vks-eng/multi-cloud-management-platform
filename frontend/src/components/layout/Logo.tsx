export function LogoMark({ className = 'h-8 w-8' }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden>
      <defs>
        <linearGradient id="co-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="100%" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <circle cx="20" cy="20" r="7" fill="url(#co-grad)" />
      <ellipse cx="20" cy="20" rx="17" ry="7" fill="none" stroke="url(#co-grad)" strokeWidth="2" transform="rotate(-28 20 20)" />
      <circle cx="34" cy="12.5" r="2.4" fill="#22d3ee" />
    </svg>
  );
}

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark />
      <div className="leading-tight">
        <p className="text-base font-semibold tracking-tight text-ink">CloudOrbit</p>
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">AWS · Azure · GCP</p>
      </div>
    </div>
  );
}
