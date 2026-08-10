interface RetryButtonProps {
  onClick: () => void;
  label?: string;
}

export function RetryButton({ onClick, label = "Réessayer" }: RetryButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="min-h-[44px] rounded-md border border-primary px-4 py-2 text-primary hover:bg-primary/5"
    >
      {label}
    </button>
  );
}
