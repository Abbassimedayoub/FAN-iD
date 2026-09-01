import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("OrganizerScannersPage listing contract", () => {
  const source = readFileSync(
    resolve(
      process.cwd(),
      "src/features/organizers/OrganizerScannersPage.tsx",
    ),
    "utf8",
  );

  it("uses a five-item server-side paginated query", () => {
    expect(source).toContain(
      "fetchOrganizerScannersPage({",
    );
    expect(source).toContain(
      "Math.ceil(scannerCount / 5)",
    );
    expect(source).toContain("Précédent");
    expect(source).toContain("Suivant");
  });

  it("resets page one when search or status changes", () => {
    expect(source).toContain(
      'placeholder="Nom, prénom ou e-mail"',
    );
    expect(source).toContain(
      'id="scanner-status-filter"',
    );

    const resetOccurrences = (
      source.match(/setScannerPage\(1\)/g) ?? []
    ).length;

    expect(resetOccurrences).toBeGreaterThanOrEqual(3);
  });

  it("keeps scanner actions in the paginated cards", () => {
    expect(source).toContain(
      "onLeaveDecision={openLeaveDecision}",
    );
    expect(source).toContain(
      "onRevoke={openRevocation}",
    );
    expect(source).toContain(
      "onArchiveSelectionChange={toggleArchiveScanner}",
    );
  });
});
