import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

const REDACTED = "***REDACTED***";

function redactSensitiveText(value: string): string {
  return value
    .replace(/Bearers+[^s,;]+/gi, `Bearer ${REDACTED}`)
    .replace(/(fanid_refresh|sessionid|csrftoken)=([^;s]+)/gi, `$1=${REDACTED}`)
    .replace(/(password|token|secret|authorization|otp)s*[:=]s*[^s,;]+/gi, `$1=${REDACTED}`)
    .replace(/eyJ[A-Za-z0-9_-]{8,}.[A-Za-z0-9_-]{8,}.[A-Za-z0-9_-]{8,}/g, REDACTED);
}

export function sanitizeErrorForLogging(
  error: Error,
  componentStack?: string | null,
): {
  name: string;
  message: string;
  componentStack: string;
} {
  return {
    name: error.name,
    message: redactSensitiveText(error.message),
    componentStack: redactSensitiveText(componentStack ?? ""),
  };
}

/**
 * Last-resort safety net for unhandled React render errors.
 * It does not replace normal per-screen error-state handling.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("fanid.error_boundary", sanitizeErrorForLogging(error, info.componentStack));
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div role="alert" className="p-8 text-center">
          <p className="font-sora text-lg font-semibold text-navy">
            Un problème est survenu. Merci de recharger la page.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
