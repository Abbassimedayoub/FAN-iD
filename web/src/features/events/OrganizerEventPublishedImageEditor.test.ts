import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const editorSource = readFileSync(
  resolve(
    process.cwd(),
    "src/features/events/OrganizerEventImageEditor.tsx",
  ),
  "utf8",
);

const detailSource = readFileSync(
  resolve(
    process.cwd(),
    "src/features/events/OrganizerEventDetailPage.tsx",
  ),
  "utf8",
);

describe("photo événement après publication", () => {
  it("autorise ajout/remplacement pour publié et reporté", () => {
    expect(editorSource).toContain(
      'event.status === "PUBLISHED"',
    );
    expect(editorSource).toContain(
      'event.status === "POSTPONED"',
    );
    expect(editorSource).toContain(
      "Ajouter une photo",
    );
    expect(editorSource).toContain(
      "Remplacer la photo",
    );
    expect(editorSource).toContain(
      "uploadEventImage(event, file)",
    );
  });

  it("conserve l’éditeur structurel séparé de la photo", () => {
    expect(detailSource).toContain(
      "<OrganizerEventImageEditor",
    );
    expect(detailSource).toContain(
      'event.status === "DRAFT"',
    );
    expect(detailSource).toContain(
      '["catalog", "event", updated.id]',
    );
  });
});
