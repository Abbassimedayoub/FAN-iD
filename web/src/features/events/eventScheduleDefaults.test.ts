import { expect, it } from "vitest";

import {
  buildEventDateTimes,
  endDateTimeThreeHoursAfter,
  endTimeThreeHoursAfter,
  eventEndsNextDay,
  isEventDateAtLeastTomorrow,
  minimumEventDate,
} from "./eventScheduleDefaults";

it("met la fin trois heures après l heure de début", () => {
  expect(endTimeThreeHoursAfter("18:00")).toBe("21:00");

  expect(endTimeThreeHoursAfter("19:15")).toBe("22:15");
});

it("interprète une heure de fin antérieure comme le lendemain", () => {
  expect(endTimeThreeHoursAfter("22:00")).toBe("01:00");

  expect(eventEndsNextDay("22:00", "02:00")).toBe(true);
  expect(eventEndsNextDay("22:00", "22:00")).toBe(true);
  expect(eventEndsNextDay("18:00", "21:00")).toBe(false);

  const schedule = buildEventDateTimes(
    "2027-12-30",
    "22:00",
    "02:00",
  );

  expect(schedule).not.toBeNull();
  expect(schedule?.endsNextDay).toBe(true);
  expect(schedule?.start).toEqual(
    new Date("2027-12-30T22:00:00"),
  );
  expect(schedule?.end).toEqual(
    new Date("2027-12-31T02:00:00"),
  );
});

it("interprète une heure de fin identique comme J+1", () => {
  const schedule = buildEventDateTimes(
    "2027-12-30",
    "22:00",
    "22:00",
  );

  expect(schedule).not.toBeNull();
  expect(schedule?.endsNextDay).toBe(true);
  expect(schedule?.end).toEqual(
    new Date("2027-12-31T22:00:00"),
  );
});

it("conserve la même date quand la fin est après le début", () => {
  const schedule = buildEventDateTimes(
    "2027-12-30",
    "18:00",
    "21:00",
  );

  expect(schedule).not.toBeNull();
  expect(schedule?.endsNextDay).toBe(false);
  expect(schedule?.end).toEqual(
    new Date("2027-12-30T21:00:00"),
  );
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
