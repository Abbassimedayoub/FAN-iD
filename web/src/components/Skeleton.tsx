/**
 * État `loading` (§4.2 Source B) : reproduit la FORME finale du contenu,
 * jamais un spinner plein écran (saut de mise en page, perception de lenteur).
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
