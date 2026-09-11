import { httpClient } from "@/lib/httpClient";

import type {
  EventAdmissionStatus,
  EventLiveDashboard,
  EventFinalReport,
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
  const firstResponse = await httpClient.get<OrganizerEventsPageResponse>("/api/v1/events", {
    params: {
      page_size: 100,
    },
  });

  const events = [...firstResponse.data.results];
  let next = firstResponse.data.next;

  // Le backend limite volontairement une réponse à 100 éléments.
  // On récupère les pages suivantes pour que les filtres et la pagination
  // de l'interface portent bien sur tous les événements de l'organisateur.
  while (next) {
    const response = await httpClient.get<OrganizerEventsPageResponse>(next);
    events.push(...response.data.results);
    next = response.data.next;
  }

  return events;
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

export async function fetchEventAdmissionStatus(eventId: string): Promise<EventAdmissionStatus> {
  const response = await httpClient.get<EventAdmissionStatus>(
    `/api/v1/access/events/${eventId}/admission`,
  );

  return response.data;
}

export async function openEventAdmission(eventId: string): Promise<EventAdmissionStatus> {
  const response = await httpClient.post<EventAdmissionStatus>(
    `/api/v1/access/events/${eventId}/admission/open`,
    {},
  );

  return response.data;
}

export async function closeEventAdmission(eventId: string): Promise<EventAdmissionStatus> {
  const response = await httpClient.post<EventAdmissionStatus>(
    `/api/v1/access/events/${eventId}/admission/close`,
    {},
  );

  return response.data;
}

export async function fetchEventLiveDashboard(eventId: string): Promise<EventLiveDashboard> {
  const response = await httpClient.get<EventLiveDashboard>(
    `/api/v1/access/events/${eventId}/live-dashboard`,
  );

  return response.data;
}

export async function fetchEventFinalReport(eventId: string): Promise<EventFinalReport> {
  const response = await httpClient.get<EventFinalReport>(
    `/api/v1/access/events/${eventId}/final-report`,
  );

  return response.data;
}
