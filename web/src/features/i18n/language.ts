import { useCallback, useEffect, useState } from "react";

export type AppLanguage = "fr" | "en";

export const LANGUAGE_STORAGE_KEY = "fanid.language";

const LANGUAGE_CHANGED_EVENT = "fanid-language-changed";

function normalizeLanguage(value: string | null | undefined): AppLanguage {
  return value === "en" ? "en" : "fr";
}

function browserStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function readAppLanguage(): AppLanguage {
  return normalizeLanguage(
    browserStorage()?.getItem(LANGUAGE_STORAGE_KEY),
  );
}

export function applyDocumentLanguage(
  language: AppLanguage,
): void {
  if (typeof document !== "undefined") {
    document.documentElement.lang = language;
  }
}

export function persistAppLanguage(
  language: AppLanguage,
): void {
  browserStorage()?.setItem(
    LANGUAGE_STORAGE_KEY,
    language,
  );

  applyDocumentLanguage(language);

  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new Event(LANGUAGE_CHANGED_EVENT),
    );
  }
}

export function useAppLanguage(): {
  language: AppLanguage;
  setLanguage: (language: AppLanguage) => void;
} {
  const [language, setLanguageState] =
    useState<AppLanguage>(() => readAppLanguage());

  useEffect(() => {
    applyDocumentLanguage(language);

    if (typeof window === "undefined") {
      return undefined;
    }

    const synchronize = (): void => {
      const next = readAppLanguage();

      applyDocumentLanguage(next);
      setLanguageState(next);
    };

    window.addEventListener(
      "storage",
      synchronize,
    );

    window.addEventListener(
      LANGUAGE_CHANGED_EVENT,
      synchronize,
    );

    return () => {
      window.removeEventListener(
        "storage",
        synchronize,
      );

      window.removeEventListener(
        LANGUAGE_CHANGED_EVENT,
        synchronize,
      );
    };
  }, [language]);

  const setLanguage = useCallback(
    (next: AppLanguage): void => {
      persistAppLanguage(next);
      setLanguageState(next);
    },
    [],
  );

  return {
    language,
    setLanguage,
  };
}
