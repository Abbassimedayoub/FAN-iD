import type { ReactElement } from "react";

import {
  type AppLanguage,
  useAppLanguage,
} from "./language";

function FranceFlag() {
  return (
    <svg
      data-testid="flag-fr"
      viewBox="0 0 27 18"
      className="h-[14px] w-[21px] overflow-hidden rounded-[2px] shadow-sm"
      aria-hidden="true"
    >
      <rect width="9" height="18" x="0" fill="#002395" />
      <rect width="9" height="18" x="9" fill="#ffffff" />
      <rect width="9" height="18" x="18" fill="#ED2939" />
    </svg>
  );
}

function UnitedKingdomFlag() {
  return (
    <svg
      data-testid="flag-en"
      viewBox="0 0 30 18"
      className="h-[14px] w-[22px] overflow-hidden rounded-[2px] shadow-sm"
      aria-hidden="true"
    >
      <rect width="30" height="18" fill="#012169" />

      <path
        d="M0 0 30 18M30 0 0 18"
        stroke="#ffffff"
        strokeWidth="5"
      />

      <path
        d="M0 0 30 18M30 0 0 18"
        stroke="#C8102E"
        strokeWidth="2"
      />

      <path
        d="M15 0v18M0 9h30"
        stroke="#ffffff"
        strokeWidth="6"
      />

      <path
        d="M15 0v18M0 9h30"
        stroke="#C8102E"
        strokeWidth="3.2"
      />
    </svg>
  );
}

const OPTIONS: ReadonlyArray<{
  language: AppLanguage;
  name: string;
  Flag: () => ReactElement;
}> = [
  {
    language: "fr",
    name: "Français",
    Flag: FranceFlag,
  },
  {
    language: "en",
    name: "English",
    Flag: UnitedKingdomFlag,
  },
];

export function LanguageSwitcher() {
  const {
    language,
    setLanguage,
  } = useAppLanguage();

  const groupLabel =
    language === "fr"
      ? "Choisir la langue"
      : "Choose language";

  return (
    <div
      role="group"
      aria-label={groupLabel}
      className="inline-flex items-center gap-0.5 rounded-xl border border-slate-200 bg-white/95 p-1 shadow-sm backdrop-blur"
    >
      {OPTIONS.map((option) => {
        const selected =
          language === option.language;

        const Flag = option.Flag;

        return (
          <button
            key={option.language}
            type="button"
            aria-label={option.name}
            aria-pressed={selected}
            title={option.name}
            onClick={() => {
              setLanguage(option.language);
            }}
            className={[
              "flex h-8 w-9 items-center justify-center rounded-lg transition",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary",
              selected
                ? "bg-primary/10 ring-1 ring-primary/25"
                : "opacity-55 hover:bg-slate-100 hover:opacity-100",
            ].join(" ")}
          >
            <Flag />
          </button>
        );
      })}
    </div>
  );
}
