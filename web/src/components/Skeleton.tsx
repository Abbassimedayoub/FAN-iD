/**
 * Loading state that mirrors the final content shape instead of showing a
 * full-screen spinner, reducing layout shifts and perceived latency.
 */
interface SkeletonProps {
  className?: string;
  "aria-label"?: string;
}

export function Skeleton({ className = "h-4 w-full", ...rest }: SkeletonProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={rest["aria-label"] ?? "Chargement en cours"}
      className={`animate-pulse rounded-md bg-navy/10 ${className}`}
    />
  );
}
