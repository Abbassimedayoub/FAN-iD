interface BrandMarkProps {
  className?: string;
  compact?: boolean;
}

export function BrandMark({ className = "", compact = false }: BrandMarkProps) {
  return (
    <div className={`inline-flex items-center gap-3 ${className}`}>
      <span
        className="relative flex h-11 w-11 items-center justify-center rounded-xl border-2 border-cyan text-cyan"
        aria-hidden="true"
      >
        <span className="absolute -left-[3px] top-1/2 h-3 w-1.5 -translate-y-1/2 rounded-r-full bg-current" />
        <span className="absolute -right-[3px] top-1/2 h-3 w-1.5 -translate-y-1/2 rounded-l-full bg-current" />

        <svg
          viewBox="0 0 24 24"
          className="h-6 w-6"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M7.5 13.5c0-2.9 2-5.2 4.5-5.2s4.5 2.3 4.5 5.2" />
          <path d="M9.2 14c0-1.8 1.2-3.3 2.8-3.3s2.8 1.5 2.8 3.3" />
          <path d="M5.4 13.4c0-4.3 2.9-7.7 6.6-7.7 3.7 0 6.6 3.4 6.6 7.7" />
          <rect x="8.3" y="13" width="7.4" height="5.8" rx="1.8" />
          <circle cx="12" cy="15.7" r=".75" fill="currentColor" stroke="none" />
          <path d="M12 16.4v1" />
        </svg>
      </span>

      {!compact ? (
        <span className="font-sora text-xl font-bold tracking-[0.18em]">FANID</span>
      ) : null}
    </div>
  );
}
