/**
 * Foundation primitives: Button, Input, Card, Table, Badge, Modal, Toast, and
 * Spinner. Accessibility targets include AA contrast, 44px touch targets,
 * visible focus, keyboard navigation, and `aria-live` for toasts.
 */
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  TableHTMLAttributes,
} from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

export function Button({
  className = "",
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
}) {
  const variantClasses: Record<ButtonVariant, string> = {
    primary: "border border-primary bg-primary text-white hover:bg-[#1256ac]",
    secondary: "!border !border-primary !bg-white !text-primary hover:!bg-[#eef5ff]",
    danger: "!border !border-red-200 !bg-red-50 !text-red-700 hover:!bg-red-100",
    ghost: "border border-transparent bg-transparent text-navy hover:bg-navy/5",
  };

  return (
    <button
      {...props}
      className={`min-h-[44px] rounded-xl px-4 py-2 text-sm font-bold transition focus:outline-none focus:ring-4 focus:ring-cyan/10 disabled:cursor-not-allowed disabled:opacity-50 ${variantClasses[variant]} ${className}`}
    />
  );
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`min-h-[44px] rounded-xl border border-[#d7e0e9] bg-white px-4 py-2.5 text-navy shadow-sm outline-none transition placeholder:text-navy/30 hover:border-navy/25 focus:border-cyan focus:ring-4 focus:ring-cyan/10 ${className}`}
    />
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-[#e4eaf0] bg-white p-4 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function Table(props: TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto">
      <table {...props} className={`w-full text-left text-sm ${props.className ?? ""}`} />
    </div>
  );
}

export type BadgeTone = "default" | "success" | "danger" | "warning" | "info" | "purple" | "muted";

export function Badge({ children, tone = "default" }: { children: ReactNode; tone?: BadgeTone }) {
  const toneClasses: Record<BadgeTone, string> = {
    default: "bg-[#eaf0f7] text-[#3c4b60]",
    success: "bg-[#e7f7f0] text-[#0b7a56]",
    danger: "bg-[#fef3f3] text-[#b91c1c]",
    warning: "bg-[#fef6e7] text-[#8a5a02]",
    info: "bg-[#eaf2fd] text-[#1663c7]",
    purple: "bg-[#f2e9fb] text-[#6b21a8]",
    muted: "bg-[#eef2f6] text-[#5b6472]",
  };

  return (
    <span
      className={`inline-flex min-h-6 items-center rounded-lg px-2.5 py-0.5 text-xs font-bold ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}

export type EventStatus =
  "DRAFT" | "PUBLISHED" | "POSTPONED" | "SUSPENDED" | "CANCELLED" | "COMPLETED" | "ARCHIVED";

const EVENT_STATUS_CONTENT: Record<EventStatus, { label: string; tone: BadgeTone }> = {
  DRAFT: { label: "Brouillon", tone: "warning" },
  PUBLISHED: { label: "Publié", tone: "success" },
  POSTPONED: { label: "Reporté", tone: "purple" },
  SUSPENDED: { label: "Suspendu", tone: "warning" },
  CANCELLED: { label: "Annulé", tone: "danger" },
  COMPLETED: { label: "Terminé", tone: "info" },
  ARCHIVED: { label: "Archivé", tone: "muted" },
};

export function EventStatusBadge({ status }: { status: EventStatus }) {
  const content = EVENT_STATUS_CONTENT[status];
  return <Badge tone={content.tone}>{content.label}</Badge>;
}

export function InlineAlert({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "success" | "warning" | "danger";
}) {
  const toneClasses = {
    info: "border-cyan/40 bg-[#f4fbfd] text-[#0a7180]",
    success: "border-[#b6e6d2] bg-[#eefaf4] text-[#0b7a56]",
    warning: "border-[#f5d9a8] bg-[#fef6e7] text-[#8a5a02]",
    danger: "border-red-200 bg-red-50 text-red-800",
  };

  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={`rounded-2xl border px-4 py-3 text-sm leading-6 ${toneClasses[tone]}`}
    >
      {children}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <section className="fanid-surface flex min-h-56 flex-col items-center justify-center px-6 py-10 text-center">
      <span
        aria-hidden="true"
        className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-[#eef4fc] text-xl text-primary"
      >
        ◌
      </span>
      <h2 className="font-sora text-lg font-bold text-navy">{title}</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-[#5b6472]">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </section>
  );
}

export function Skeleton({
  className = "",
  label = "Chargement",
}: {
  className?: string;
  label?: string;
}) {
  return (
    <span
      role="status"
      aria-label={label}
      className={`block animate-pulse rounded-xl bg-[#eaf0f7] ${className}`}
    />
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-center justify-center bg-navy/40"
    >
      <Card className="w-full max-w-md">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-sora text-lg font-semibold text-navy">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer"
            className="min-h-[44px] min-w-[44px]"
          >
            ×
          </button>
        </div>
        {children}
      </Card>
    </div>
  );
}

export function Toast({
  message,
  tone = "default",
}: {
  message: string;
  tone?: "default" | "success" | "danger";
}) {
  const toneClasses: Record<string, string> = {
    default: "bg-navy text-white",
    success: "bg-emerald-600 text-white",
    danger: "bg-red-600 text-white",
  };
  return (
    <div
      role="status"
      aria-live="polite"
      className={`rounded-md px-4 py-2 text-sm ${toneClasses[tone]}`}
    >
      {message}
    </div>
  );
}

export function Spinner({ label = "Chargement" }: { label?: string }) {
  return (
    <span
      role="status"
      aria-label={label}
      className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent"
    />
  );
}
