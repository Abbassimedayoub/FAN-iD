import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("OrganizerArchivedScannersPage listing contract", () => {
  const source = readFileSync(
    resolve(process.cwd(), "src/features/organizers/OrganizerArchivedScannersPage.tsx"),
    "utf8",
  );

  it("uses server pagination fixed to five archives", () => {
    expect(source).toContain("fetchOrganizerArchivedScannersPage({");
    expect(source).toContain("Math.ceil(archiveCount / 5)");
    expect(source).toContain("Précédent");
    expect(source).toContain("Suivant");
  });

  it("supports archive search and terminal status filter", () => {
    expect(source).toContain('id="archive-scanner-search"');
    expect(source).toContain('placeholder="Nom, prénom ou e-mail"');
    expect(source).toContain('id="archive-scanner-status"');
    expect(source).toContain('value="INVITATION_CANCELLED"');
    expect(source).toContain('value="DELETED"');
  });

  it("resets archive page after search or filter changes", () => {
    const resets = (source.match(/setArchivePage\(1\)/g) ?? []).length;

    expect(resets).toBeGreaterThanOrEqual(2);
  });

  it("keeps archived scanner history and reinvitation", () => {
    expect(source).toContain("Invitation créée");
    expect(source).toContain("Retrait de l’équipe");
    expect(source).toContain("Archivage");
    expect(source).toContain("Réinviter ce scanner");
  });
});
