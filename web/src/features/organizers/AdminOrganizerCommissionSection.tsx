import { useState } from "react";

import { Button } from "@/components/primitives";

import { AdminOrganizerCommissionPanel } from "./AdminOrganizerCommissionPanel";
import type { Organizer } from "./types";

export function AdminOrganizerCommissionSection({ organizer }: { organizer: Organizer }) {
  const [open, setOpen] = useState(false);

  return (
    <section
      aria-labelledby="admin-organizer-commission-title"
      className="mx-auto w-full max-w-4xl px-6 pb-8 md:px-8"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-primary">Commission</p>
          <h2
            id="admin-organizer-commission-title"
            className="mt-1 font-sora text-xl font-bold text-navy"
          >
            Accord Organizer ↔ FANID
          </h2>
        </div>

        <Button type="button" onClick={() => setOpen((current) => !current)}>
          {open ? "Masquer la négociation" : "Gérer la commission"}
        </Button>
      </div>

      {open ? <AdminOrganizerCommissionPanel organizer={organizer} /> : null}
    </section>
  );
}
