import fs from "node:fs";
import path from "node:path";

import { expect, it } from "vitest";

it("résout les URLs image API dans la liste organizer", () => {
  const source = fs.readFileSync(
    path.resolve(process.cwd(), "src/features/events/OrganizerEventsPage.tsx"),
    "utf8",
  );

  expect(source).toContain('from "./eventImageUrl"');

  expect(source).toMatch(/eventImageUrl\s*\(\s*event\.image_url\s*\)/);

  expect(source).not.toContain("src={event.image_url}");
});
