export function endTimeThreeHoursAfter(startTime: string): string {
  const match = /^(\d{2}):(\d{2})$/.exec(startTime);

  if (!match) {
    return "";
  }

  const hours = Number(match[1]);
  const minutes = Number(match[2]);

  if (
    !Number.isInteger(hours) ||
    !Number.isInteger(minutes) ||
    hours < 0 ||
    hours > 23 ||
    minutes < 0 ||
    minutes > 59
  ) {
    return "";
  }

  const totalMinutes = hours * 60 + minutes + 180;
  const normalized = totalMinutes % (24 * 60);

  const endHours = Math.floor(normalized / 60);
  const endMinutes = normalized % 60;

  return `${String(endHours).padStart(2, "0")}:${String(endMinutes).padStart(2, "0")}`;
}

export function endDateTimeThreeHoursAfter(startsAt: string): string {
  if (!startsAt) {
    return "";
  }

  const start = new Date(startsAt);

  if (Number.isNaN(start.getTime())) {
    return "";
  }

  start.setHours(start.getHours() + 3);

  const pad = (value: number): string => String(value).padStart(2, "0");

  return [
    start.getFullYear(),
    "-",
    pad(start.getMonth() + 1),
    "-",
    pad(start.getDate()),
    "T",
    pad(start.getHours()),
    ":",
    pad(start.getMinutes()),
  ].join("");
}
