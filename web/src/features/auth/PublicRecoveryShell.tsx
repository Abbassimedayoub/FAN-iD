import type { ReactNode } from "react";

import { BrandMark } from "@/components/BrandMark";

interface PublicRecoveryShellProps {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}

export function PublicRecoveryShell({
  eyebrow,
  title,
  description,
  children,
}: PublicRecoveryShellProps) {
  return (
    <main className="min-h-screen bg-[#eef4f9] p-4 sm:p-6 lg:p-8">
      <section className="mx-auto grid min-h-[calc(100vh-2rem)] w-full max-w-[1500px] overflow-hidden rounded-[28px] border border-white/70 bg-white shadow-[0_30px_90px_rgba(14,42,77,0.12)] sm:min-h-[calc(100vh-3rem)] lg:grid-cols-[0.92fr_1.08fr]">
        <aside className="relative hidden overflow-hidden bg-[#0b3157] px-10 py-12 text-white lg:flex lg:flex-col lg:justify-between xl:px-14 xl:py-14">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full border border-cyan/10"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -left-10 -top-10 h-48 w-48 rounded-full border border-cyan/10"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -bottom-40 right-[-100px] h-[420px] w-[420px] rounded-full border border-cyan/10"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -bottom-24 right-[-30px] h-[270px] w-[270px] rounded-full border border-cyan/10"
          />

          <BrandMark className="relative z-10 text-white" />

          <div className="relative z-10 max-w-xl pb-10">
            <BrandMark compact className="mb-8" />

            <h1 className="font-sora text-4xl font-bold leading-[1.12] tracking-[-0.03em] xl:text-5xl">
              Votre compte.
              <br />
              Toujours sécurisé.
            </h1>

            <p className="mt-7 max-w-md text-sm leading-7 text-white/60">
              Retrouvez votre accès FANID grâce à un lien sécurisé ou à un code temporaire envoyé
              directement dans votre boîte e-mail.
            </p>
          </div>

          <p className="relative z-10 text-xs text-white/35">FANID · Secure ticketing platform</p>
        </aside>

        <div className="relative flex items-center justify-center px-5 py-12 sm:px-10 lg:px-14 xl:px-20">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute right-[-120px] top-[-120px] h-80 w-80 rounded-full bg-cyan/5 blur-3xl"
          />

          <div className="relative z-10 w-full max-w-[460px]">
            <div className="mb-9 lg:hidden">
              <BrandMark className="text-navy" />
            </div>

            <div className="mb-7">
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-primary">
                {eyebrow}
              </p>

              <h2 className="font-sora text-3xl font-bold tracking-[-0.03em] text-navy">{title}</h2>

              <p className="mt-3 text-sm leading-6 text-navy/55">{description}</p>
            </div>

            {children}

            <div className="mt-5 flex items-start gap-3 rounded-2xl border border-cyan/20 bg-cyan/5 px-4 py-3">
              <span
                aria-hidden="true"
                className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan/15 text-xs"
              >
                🔒
              </span>

              <p className="text-xs leading-5 text-navy/55">
                Le lien et le code sont temporaires, à usage unique et expirent automatiquement
                après 15 minutes.
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
