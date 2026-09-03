import { expect, it } from "vitest";

import {
  endDateTimeThreeHoursAfter,
  endTimeThreeHoursAfter,
  isEventDateAtLeastTomorrow,
  minimumEventDate,
} from "./eventScheduleDefaults";

it("met la fin trois heures après l heure de début", () => {
  expect(endTimeThreeHoursAfter("18:00")).toBe("21:00");

  expect(endTimeThreeHoursAfter("19:15")).toBe("22:15");
});

it("synchronise date et heure trois heures après", () => {
  expect(endDateTimeThreeHoursAfter("2027-12-30T18:00")).toBe("2027-12-30T21:00");

  expect(endDateTimeThreeHoursAfter("2027-12-31T10:30")).toBe("2027-12-31T13:30");
});

it("impose demain comme date minimale", () => {
  const reference = new Date(2026, 8, 3, 23, 30, 0);

  expect(minimumEventDate(reference)).toBe("2026-09-04");
  expect(isEventDateAtLeastTomorrow("2026-09-03", reference)).toBe(false);
  expect(isEventDateAtLeastTomorrow("2026-09-04", reference)).toBe(true);
  expect(isEventDateAtLeastTomorrow("2026-09-05", reference)).toBe(true);
});
