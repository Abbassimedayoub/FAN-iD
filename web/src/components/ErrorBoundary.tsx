import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

/**
 * Filet de sécurité ultime — capture les erreurs de rendu React non gérées
 * par le contrat d'états d'écran (§4.2 Source B). Ne remplace PAS la gestion
 * d'état `error` par écran, qui reste la voie normale.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("fanid.error_boundary", error, info.componentStack);
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
