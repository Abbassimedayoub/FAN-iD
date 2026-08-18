/**
 * Primitives socles restantes (§4.3 Source B) : Button, Input, Card, Table,
 * Badge, Modal, Toast, Spinner. Accessibilité WCAG 2.1 AA : contraste ≥
 * 4.5:1 (tokens Tailwind validés), cibles ≥ 44px, focus visible (styles.css),
 * navigation clavier, `aria-live` pour les toasts.
 */
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  TableHTMLAttributes,
} from "react";

export function Button({ className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`min-h-[44px] rounded-md bg-primary px-4 py-2 text-white disabled:opacity-50 ${className}`}
    />
  );
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`min-h-[44px] rounded-md border border-navy/20 px-3 py-2 focus:border-primary ${className}`}
    />
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-navy/10 bg-white p-4 shadow-sm ${className}`}>
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

export function Badge({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: "default" | "success" | "danger";
}) {
  const toneClasses: Record<string, string> = {
    default: "bg-navy/10 text-navy",
    success: "bg-emerald-100 text-emerald-800",
    danger: "bg-red-100 text-red-800",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${toneClasses[tone]}`}>
      {children}
    </span>
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
