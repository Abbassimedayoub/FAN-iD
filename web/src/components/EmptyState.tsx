/** État `empty` (§4.2 Source B) : illustration + phrase explicative + action principale. */
interface EmptyStateProps {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ title, description, actionLabel, onAction }: EmptyStateProps) {
  return (
    <div role="status" className="flex flex-col items-center gap-3 py-12 text-center">
      <div aria-hidden="true" className="h-16 w-16 rounded-full bg-navy/10" />
      <p className="font-sora text-lg font-semibold text-navy">{title}</p>
      {description ? <p className="max-w-sm text-sm text-navy/70">{description}</p> : null}
      {actionLabel && onAction ? (
        <button
          type="button"
          onClick={onAction}
          className="mt-2 min-h-[44px] rounded-md bg-primary px-4 py-2 text-white"
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
