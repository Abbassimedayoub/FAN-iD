import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { Button, Card, Input, Spinner } from "@/components/primitives";
import { OrganizerShell } from "@/features/organizers/OrganizerShell";

import { fetchEventCategories, fetchOrganizerEvent, updateEventDraft } from "./api";
import type { EventDraftInput, OrganizerEvent } from "./types";
import { endTimeThreeHoursAfter } from "./eventScheduleDefaults";

function localDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const year = date.getFullYear();

  const month = String(date.getMonth() + 1).padStart(2, "0");

  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function localTime(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const hours = String(date.getHours()).padStart(2, "0");

  const minutes = String(date.getMinutes()).padStart(2, "0");

  return `${hours}:${minutes}`;
}

function EventEditor({ event }: { event: OrganizerEvent }) {
  const [current, setCurrent] = useState(event);

  const [name, setName] = useState(event.name);

  const [description, setDescription] = useState(event.description);

  const [categoryId, setCategoryId] = useState(event.category_id);

  const [date, setDate] = useState(localDate(event.starts_at));

  const [startTime, setStartTime] = useState(localTime(event.starts_at));

  const [endTime, setEndTime] = useState(localTime(event.ends_at));

  const [venue, setVenue] = useState(event.venue);

  const [capacity, setCapacity] = useState(
    event.capacity_total === null ? "" : String(event.capacity_total),
  );

  const [pending, setPending] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [success, setSuccess] = useState(false);

  const categoriesQuery = useQuery({
    queryKey: ["catalog", "event-categories"],
    queryFn: fetchEventCategories,
  });

  useEffect(() => {
    setCurrent(event);
  }, [event]);

  async function save(): Promise<void> {
    setError(null);
    setSuccess(false);

    if (!name.trim() || !categoryId || !date || !startTime || !endTime) {
      setError("Le nom, la catégorie, la date et les horaires sont requis.");
      return;
    }

    const start = new Date(`${date}T${startTime}:00`);

    const end = new Date(`${date}T${endTime}:00`);

    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || end <= start) {
      setError("L’heure de fin doit être postérieure à l’heure de début.");
      return;
    }

    let capacityTotal: number | null = null;

    if (capacity.trim() !== "") {
      capacityTotal = Number(capacity);

      if (!Number.isInteger(capacityTotal) || capacityTotal < 1) {
        setError("La capacité doit être un entier positif.");
        return;
      }
    }

    const payload: EventDraftInput = {
      category_id: categoryId,
      name: name.trim(),
      description: description.trim(),
      starts_at: start.toISOString(),
      ends_at: end.toISOString(),
      venue: venue.trim(),
      capacity_total: capacityTotal,
    };

    setPending(true);

    try {
      const updated = await updateEventDraft(current, payload);

      setCurrent(updated);
      setSuccess(true);
    } catch {
      setError(
        "Impossible d’enregistrer les modifications. Le brouillon a peut-être été modifié ailleurs.",
      );
    } finally {
      setPending(false);
    }
  }

  if (current.status !== "DRAFT") {
    return (
      <Card className="p-8 text-center">
        <h1 className="font-sora text-2xl font-bold text-[#30445b]">Événement non modifiable</h1>

        <p className="mt-3 text-sm leading-6 text-[#758597]">
          Seuls les événements en brouillon peuvent modifier leurs informations structurelles.
        </p>

        <Link
          to={`/organizer/events/${current.id}`}
          className="mt-6 inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[#1769d2] px-5 text-sm font-semibold text-white"
        >
          Voir l’événement
        </Link>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden border-[#e1e7ed] p-0">
      <div className="border-b border-[#edf0f3] px-6 py-5 sm:px-8">
        <h1 className="font-sora text-xl font-bold text-[#30445b]">Modifier l’événement</h1>

        <p className="mt-1 text-sm text-[#8491a0]">Modifiez les informations du brouillon.</p>
      </div>

      <div className="space-y-5 px-6 py-6 sm:px-8">
        <div>
          <label
            htmlFor="edit-event-name"
            className="mb-2 block text-sm font-semibold text-[#40556b]"
          >
            Nom de l’événement
          </label>

          <Input
            id="edit-event-name"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
            }}
            className="w-full"
          />
        </div>

        <div>
          <label
            htmlFor="edit-event-description"
            className="mb-2 block text-sm font-semibold text-[#40556b]"
          >
            Description
          </label>

          <textarea
            id="edit-event-description"
            rows={4}
            value={description}
            onChange={(e) => {
              setDescription(e.target.value);
            }}
            className="w-full rounded-xl border border-[#d7e0e9] bg-white px-4 py-3 text-sm text-navy outline-none focus:border-cyan focus:ring-4 focus:ring-cyan/10"
          />
        </div>

        <div>
          <label
            htmlFor="edit-event-category"
            className="mb-2 block text-sm font-semibold text-[#40556b]"
          >
            Catégorie de l’événement
          </label>

          <select
            id="edit-event-category"
            value={categoryId}
            onChange={(e) => {
              setCategoryId(e.target.value);
            }}
            className="min-h-[44px] w-full rounded-xl border border-[#d7e0e9] bg-white px-4 text-sm text-navy"
          >
            {categoriesQuery.data?.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <label
              htmlFor="edit-event-date"
              className="mb-2 block text-sm font-semibold text-[#40556b]"
            >
              Date
            </label>

            <Input
              id="edit-event-date"
              type="date"
              value={date}
              onChange={(e) => {
                setDate(e.target.value);
              }}
              className="w-full"
            />
          </div>

          <div>
            <label
              htmlFor="edit-event-start"
              className="mb-2 block text-sm font-semibold text-[#40556b]"
            >
              Heure de début
            </label>

            <Input
              id="edit-event-start"
              type="time"
              value={startTime}
              onChange={(e) => {
                const nextStartTime = e.target.value;

                setStartTime(nextStartTime);

                const nextAutomaticEndTime = endTimeThreeHoursAfter(nextStartTime);

                if (nextAutomaticEndTime) {
                  setEndTime(nextAutomaticEndTime);
                }
              }}
              className="w-full"
            />
          </div>

          <div>
            <label
              htmlFor="edit-event-end"
              className="mb-2 block text-sm font-semibold text-[#40556b]"
            >
              Heure de fin
            </label>

            <Input
              id="edit-event-end"
              type="time"
              value={endTime}
              onChange={(e) => {
                setEndTime(e.target.value);
              }}
              className="w-full"
            />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label
              htmlFor="edit-event-venue"
              className="mb-2 block text-sm font-semibold text-[#40556b]"
            >
              Lieu
            </label>

            <Input
              id="edit-event-venue"
              value={venue}
              onChange={(e) => {
                setVenue(e.target.value);
              }}
              className="w-full"
            />
          </div>

          <div>
            <label
              htmlFor="edit-event-capacity"
              className="mb-2 block text-sm font-semibold text-[#40556b]"
            >
              Capacité totale
            </label>

            <Input
              id="edit-event-capacity"
              inputMode="numeric"
              value={capacity}
              onChange={(e) => {
                setCapacity(e.target.value);
              }}
              className="w-full"
            />
          </div>
        </div>

        {error ? (
          <p
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </p>
        ) : null}

        {success ? (
          <p
            role="status"
            className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700"
          >
            Modifications enregistrées.
          </p>
        ) : null}
      </div>

      <div className="flex flex-col-reverse gap-3 border-t border-[#edf0f3] bg-[#fbfcfd] px-6 py-5 sm:flex-row sm:justify-between sm:px-8">
        <Link
          to="/organizer/events"
          className="inline-flex min-h-[44px] items-center justify-center rounded-xl px-4 text-sm font-semibold text-[#657588] hover:bg-[#eef2f6]"
        >
          Annuler
        </Link>

        <Button
          type="button"
          disabled={pending}
          onClick={() => {
            void save();
          }}
          className="bg-[#1769d2] px-6 font-semibold hover:bg-[#125bb9]"
        >
          {pending ? "Enregistrement…" : "Enregistrer les modifications"}
        </Button>
      </div>
    </Card>
  );
}

export function OrganizerEventEditPage() {
  const { eventId } = useParams<{
    eventId: string;
  }>();

  const query = useQuery({
    queryKey: ["catalog", "event", eventId],
    queryFn: () => {
      if (!eventId) {
        throw new Error("EVENT_ID_REQUIRED");
      }

      return fetchOrganizerEvent(eventId);
    },
    enabled: Boolean(eventId),
  });

  const breadcrumbs = (
    <div className="flex items-center gap-2 text-sm">
      <Link to="/organizer/events" className="font-medium text-[#8a96a5] hover:text-[#1769d2]">
        Événements
      </Link>

      <span aria-hidden="true" className="text-[#b4bdc8]">
        /
      </span>

      <span className="font-semibold text-[#34465c]">Modifier</span>
    </div>
  );

  return (
    <OrganizerShell activeItem="events" breadcrumbs={breadcrumbs}>
      <main className="px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
        <div className="mx-auto max-w-[980px]">
          {query.isPending ? (
            <div className="flex min-h-[420px] items-center justify-center">
              <Spinner label="Chargement de l’événement" />
            </div>
          ) : query.isError || !query.data ? (
            <Card className="p-8 text-center">
              <h1 className="font-sora text-2xl font-bold text-[#30445b]">Événement introuvable</h1>

              <Link
                to="/organizer/events"
                className="mt-5 inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[#1769d2] px-5 text-sm font-semibold text-white"
              >
                Retour aux événements
              </Link>
            </Card>
          ) : (
            <EventEditor event={query.data} />
          )}
        </div>
      </main>
    </OrganizerShell>
  );
}
