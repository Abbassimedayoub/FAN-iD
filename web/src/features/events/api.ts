import { httpClient } from "@/lib/httpClient";

import type {
  EventCancelInput,
  EventCategory,
  EventDraftInput,
  EventPostponeInput,
  EventScannerAssignment,
  EventSuspendInput,
  OrganizerEvent,
} from "./types";

export async function fetchEventCategories(): Promise<EventCategory[]> {
  const response = await httpClient.get<EventCategory[]>("/api/v1/categories");

  return response.data;
}

export async function createEventCategory(name: string): Promise<EventCategory> {
  const response = await httpClient.post<EventCategory>("/api/v1/categories", {
    name: name.trim(),
  });

  return response.data;
}

export async function deleteEventCategory(categoryId: string): Promise<void> {
  await httpClient.delete(`/api/v1/categories/${categoryId}`);
}

export async function createEventDraft(input: EventDraftInput): Promise<OrganizerEvent> {
  const response = await httpClient.post<OrganizerEvent>("/api/v1/events", input);

  return response.data;
}

export async function updateEventDraft(
  event: OrganizerEvent,
  input: EventDraftInput,
): Promise<OrganizerEvent> {
  const response = await httpClient.patch<OrganizerEvent>(`/api/v1/events/${event.id}`, input, {
    headers: {
      "If-Match": `"${event.version}"`,
    },
  });

  return response.data;
}

export async function deleteEventDraft(event: OrganizerEvent): Promise<void> {
  await httpClient.delete(`/api/v1/events/${event.id}`, {
    headers: {
      "If-Match": `"${event.version}"`,
    },
  });
}

export async function uploadEventImage(
  event: OrganizerEvent,
  image: File,
): Promise<OrganizerEvent> {
  const payload = new FormData();
  payload.append("image", image);

  const response = await httpClient.put<OrganizerEvent>(
    `/api/v1/events/${event.id}/image`,
    payload,
    {
      headers: {
        "If-Match": `"${event.version}"`,
      },
    },
  );

  return response.data;
}

export async function fetchTicketCategories(
  eventId: string,
): Promise<import("./types").TicketCategory[]> {
  const response = await httpClient.get<import("./types").TicketCategory[]>(
    `/api/v1/events/${eventId}/ticket-categories`,
  );

  return response.data;
}

export async function createTicketCategory(
  eventId: string,
  input: import("./types").TicketCategoryInput,
): Promise<import("./types").TicketCategory> {
  const response = await httpClient.post<import("./types").TicketCategory>(
    `/api/v1/events/${eventId}/ticket-categories`,
    input,
  );

  return response.data;
}

export async function updateTicketCategory(
  category: import("./types").TicketCategory,
  input: import("./types").TicketCategoryInput,
): Promise<import("./types").TicketCategory> {
  const response = await httpClient.patch<import("./types").TicketCategory>(
    `/api/v1/events/${category.event_id}/ticket-categories/${category.id}`,
    input,
    {
      headers: {
        "If-Match": `"${category.version}"`,
      },
    },
  );

  return response.data;
}

export async function deleteTicketCategory(
  category: import("./types").TicketCategory,
): Promise<void> {
  await httpClient.delete(`/api/v1/events/${category.event_id}/ticket-categories/${category.id}`, {
    headers: {
      "If-Match": `"${category.version}"`,
    },
  });
}

export async function publishEvent(event: OrganizerEvent): Promise<OrganizerEvent> {
  const response = await httpClient.post<OrganizerEvent>(
    `/api/v1/events/${event.id}/publish`,
    {},
    {
      headers: {
        "If-Match": `"${event.version}"`,
      },
    },
  );

  return response.data;
}

interface OrganizerEventsPageResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: OrganizerEvent[];
}

export async function fetchOrganizerEvents(): Promise<OrganizerEvent[]> {
  const response = await httpClient.get<OrganizerEventsPageResponse>("/api/v1/events");

  return response.data.results;
}

export async function fetchOrganizerEvent(eventId: string): Promise<OrganizerEvent> {
  const response = await httpClient.get<OrganizerEvent>(`/api/v1/events/${eventId}`);

  return response.data;
}

export async function archiveEvent(event: OrganizerEvent): Promise<OrganizerEvent> {
  const response = await httpClient.post<OrganizerEvent>(
    `/api/v1/events/${event.id}/archive`,
    {},
    {
      headers: {
        "If-Match": `"${event.version}"`,
      },
    },
  );

  return response.data;
}

export async function unarchiveEvent(event: OrganizerEvent): Promise<OrganizerEvent> {
  const response = await httpClient.post<OrganizerEvent>(
    `/api/v1/events/${event.id}/unarchive`,
    {},
    {
      headers: {
        "If-Match": `"${event.version}"`,
      },
    },
  );

  return response.data;
}

export async function postponeEvent(
  event: OrganizerEvent,
  input: EventPostponeInput,
): Promise<OrganizerEvent> {
  const response = await httpClient.post<OrganizerEvent>(
    `/api/v1/events/${event.id}/postpone`,
    input,
    {
      headers: {
        "If-Match": `"${event.version}"`,
      },
    },
  );

  return response.data;
}

export async function suspendEvent(
  event: OrganizerEvent,
  input: EventSuspendInput,
): Promise<OrganizerEvent> {
  const response = await httpClient.post<OrganizerEvent>(
    `/api/v1/events/${event.id}/suspend`,
    input,
    {
      headers: {
        "If-Match": `"${event.version}"`,
      },
    },
  );

  return response.data;
}

export async function cancelEvent(
  event: OrganizerEvent,
  input: EventCancelInput,
): Promise<OrganizerEvent> {
  const response = await httpClient.post<OrganizerEvent>(
    `/api/v1/events/${event.id}/cancel`,
    input,
    {
      headers: {
        "If-Match": `"${event.version}"`,
      },
    },
  );

  return response.data;
}

export async function fetchEventScannerAssignments(
  eventId: string,
): Promise<EventScannerAssignment[]> {
  const response = await httpClient.get<EventScannerAssignment[]>(
    `/api/v1/events/${eventId}/scanners`,
  );

  return response.data;
}

export async function assignEventScanner(
  eventId: string,
  scannerId: string,
): Promise<EventScannerAssignment> {
  const response = await httpClient.post<EventScannerAssignment>(
    `/api/v1/events/${eventId}/scanners`,
    {
      scanner_id: scannerId,
    },
  );

  return response.data;
}

export async function unassignEventScanner(eventId: string, scannerId: string): Promise<void> {
  await httpClient.delete(`/api/v1/events/${eventId}/scanners/${scannerId}`);
}
