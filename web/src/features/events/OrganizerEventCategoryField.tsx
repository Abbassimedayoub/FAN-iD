import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Input, Modal } from "@/components/primitives";

import { createEventCategory, deleteEventCategory } from "./api";
import type { EventCategory } from "./types";

const EVENT_CATEGORIES_QUERY_KEY = ["catalog", "event-categories"] as const;

interface OrganizerEventCategoryFieldProps {
  categories: EventCategory[];
  isPending: boolean;
  isError: boolean;
  value: string;
  validationMessage?: string;
  onChange: (categoryId: string) => void;
}

function categoryActionError(error: unknown): string {
  if (typeof error === "object" && error !== null && "code" in error) {
    const code = (
      error as {
        code?: unknown;
      }
    ).code;

    switch (code) {
      case "CATEGORY_ALREADY_EXISTS":
        return "Une catégorie portant ce nom existe déjà.";
      case "CATEGORY_IN_USE":
        return "Cette catégorie est utilisée par un événement et ne peut pas être supprimée.";
      case "ORGANIZER_NOT_APPROVED":
        return "Votre organisation doit être approuvée pour gérer les catégories.";
      case "NETWORK_ERROR":
        return "Connexion au serveur impossible. Réessayez.";
      case "VALIDATION_ERROR":
        return "Vérifiez le nom de la catégorie.";
    }
  }

  return "Impossible de gérer cette catégorie pour le moment.";
}

function TrashIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <path d="M3 6h18" />
      <path d="M8 6V4h8v2" />
      <path d="M19 6l-1 14H6L5 6" />
      <path d="M10 11v5" />
      <path d="M14 11v5" />
    </svg>
  );
}

export function OrganizerEventCategoryField({
  categories,
  isPending,
  isError,
  value,
  validationMessage,
  onChange,
}: OrganizerEventCategoryFieldProps) {
  const queryClient = useQueryClient();

  const [creatorOpen, setCreatorOpen] = useState(false);

  const [categoryName, setCategoryName] = useState("");

  const [creating, setCreating] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<EventCategory | null>(null);

  const [deleting, setDeleting] = useState(false);

  const [actionError, setActionError] = useState<string | null>(null);

  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const ownCategories = useMemo(
    () => categories.filter((category) => category.is_owned_by_me === true),
    [categories],
  );

  function updateCategoryCache(updater: (current: EventCategory[]) => EventCategory[]): void {
    queryClient.setQueryData<EventCategory[]>(EVENT_CATEGORIES_QUERY_KEY, (current) =>
      updater(current ?? categories),
    );
  }

  async function createCategory(): Promise<void> {
    const normalizedName = categoryName.trim();

    setActionError(null);
    setActionSuccess(null);

    if (!normalizedName) {
      setActionError("Saisissez le nom de la nouvelle catégorie.");
      return;
    }

    if (normalizedName.length > 120) {
      setActionError("Le nom de la catégorie ne doit pas dépasser 120 caractères.");
      return;
    }

    setCreating(true);

    try {
      const created = await createEventCategory(normalizedName);

      updateCategoryCache((current) =>
        [...current.filter((category) => category.id !== created.id), created].sort((left, right) =>
          left.name.localeCompare(right.name, "fr"),
        ),
      );

      onChange(created.id);

      setCategoryName("");
      setCreatorOpen(false);

      setActionSuccess(`Catégorie « ${created.name} » ajoutée et sélectionnée.`);
    } catch (error) {
      setActionError(categoryActionError(error));
    } finally {
      setCreating(false);
    }
  }

  async function confirmDelete(): Promise<void> {
    if (!deleteTarget || !deleteTarget.can_delete) {
      return;
    }

    setDeleting(true);
    setActionError(null);
    setActionSuccess(null);

    try {
      await deleteEventCategory(deleteTarget.id);

      updateCategoryCache((current) =>
        current.filter((category) => category.id !== deleteTarget.id),
      );

      if (value === deleteTarget.id) {
        onChange("");
      }

      setActionSuccess(`Catégorie « ${deleteTarget.name} » supprimée.`);

      setDeleteTarget(null);
    } catch (error) {
      setActionError(categoryActionError(error));

      await queryClient.invalidateQueries({
        queryKey: EVENT_CATEGORIES_QUERY_KEY,
      });

      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <label htmlFor="event-category" className="block text-[13px] font-semibold text-[#33465c]">
          Catégorie de l’événement
        </label>

        <button
          type="button"
          aria-expanded={creatorOpen}
          onClick={() => {
            setCreatorOpen((current) => !current);
            setActionError(null);
            setActionSuccess(null);
          }}
          className="inline-flex min-h-9 items-center justify-center rounded-lg px-3 text-xs font-semibold text-[#1769d2] transition hover:bg-[#1769d2]/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1769d2]"
        >
          + Ajouter une catégorie
        </button>
      </div>

      <select
        id="event-category"
        disabled={isPending}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={validationMessage ? "true" : "false"}
        className="min-h-[46px] w-full rounded-xl border border-[#d7e0e9] bg-white px-4 py-2.5 text-sm text-navy shadow-sm outline-none transition focus:border-cyan focus:ring-4 focus:ring-cyan/10 disabled:bg-[#f5f7f9]"
      >
        <option value="">{isPending ? "Chargement..." : "Sélectionner une catégorie"}</option>

        {categories.map((category) => (
          <option key={category.id} value={category.id}>
            {category.name}
          </option>
        ))}
      </select>

      {validationMessage ? (
        <p role="alert" className="mt-1.5 text-xs font-medium text-red-600">
          {validationMessage}
        </p>
      ) : null}

      {isError ? (
        <p role="alert" className="mt-1.5 text-xs font-medium text-red-600">
          Impossible de charger les catégories.
        </p>
      ) : null}

      {creatorOpen ? (
        <div className="mt-3 rounded-xl border border-[#dce5ed] bg-[#f8fafc] p-4">
          <label
            htmlFor="new-event-category"
            className="mb-2 block text-xs font-semibold text-[#33465c]"
          >
            Nom de la nouvelle catégorie
          </label>

          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              id="new-event-category"
              value={categoryName}
              maxLength={120}
              disabled={creating}
              placeholder="Ex. Concert, Festival, Conférence..."
              className="min-w-0 flex-1"
              onChange={(event) => setCategoryName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void createCategory();
                }
              }}
            />

            <button
              type="button"
              disabled={creating}
              onClick={() => {
                void createCategory();
              }}
              className="inline-flex min-h-[46px] items-center justify-center rounded-xl bg-[#1769d2] px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#125dbd] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {creating ? "Création..." : "Créer la catégorie"}
            </button>
          </div>

          <p className="mt-2 text-[11px] leading-5 text-[#8492a3]">
            Cette catégorie sera disponible immédiatement dans la liste et restera associée à votre
            organisation.
          </p>
        </div>
      ) : null}

      {ownCategories.length > 0 ? (
        <div className="mt-4 rounded-xl border border-[#e3e9ef] bg-white p-4">
          <div className="mb-3">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#718096]">
              Mes catégories personnalisées
            </p>
            <p className="mt-1 text-[11px] leading-5 text-[#98a2ad]">
              Une catégorie utilisée par un événement est conservée et ne peut plus être supprimée.
            </p>
          </div>

          <div className="space-y-2">
            {ownCategories.map((category) => (
              <div
                key={category.id}
                className="flex min-h-11 items-center justify-between gap-3 rounded-lg border border-[#edf1f4] bg-[#fbfcfd] px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-[#33465c]">{category.name}</p>

                  {!category.can_delete ? (
                    <p className="mt-0.5 text-[11px] text-[#8a96a4]">Utilisée par un événement</p>
                  ) : null}
                </div>

                {category.can_delete ? (
                  <button
                    type="button"
                    aria-label={`Supprimer la catégorie ${category.name}`}
                    title="Supprimer cette catégorie"
                    onClick={() => {
                      setActionError(null);
                      setActionSuccess(null);
                      setDeleteTarget(category);
                    }}
                    className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-red-600 transition hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                  >
                    <TrashIcon />
                  </button>
                ) : (
                  <span className="shrink-0 rounded-full bg-[#eef2f6] px-2.5 py-1 text-[10px] font-semibold text-[#788594]">
                    Protégée
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {actionSuccess ? (
        <p
          role="status"
          className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800"
        >
          {actionSuccess}
        </p>
      ) : null}

      {actionError ? (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700"
        >
          {actionError}
        </p>
      ) : null}

      <Modal
        open={deleteTarget !== null}
        title="Supprimer la catégorie ?"
        onClose={() => {
          if (!deleting) {
            setDeleteTarget(null);
          }
        }}
      >
        <p className="text-sm leading-6 text-navy/65">
          {deleteTarget
            ? `La catégorie « ${deleteTarget.name} » sera supprimée définitivement.`
            : ""}
        </p>

        <p className="mt-2 text-xs leading-5 text-navy/45">
          Cette action est possible uniquement parce qu’aucun événement n’utilise actuellement cette
          catégorie.
        </p>

        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            disabled={deleting}
            onClick={() => setDeleteTarget(null)}
            className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#d8e0e8] bg-white px-4 text-sm font-semibold text-[#526276] transition hover:bg-[#f7f9fb] disabled:opacity-60"
          >
            Annuler
          </button>

          <button
            type="button"
            disabled={deleting}
            onClick={() => {
              void confirmDelete();
            }}
            className="inline-flex min-h-11 items-center justify-center rounded-xl bg-red-600 px-4 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-60"
          >
            {deleting ? "Suppression..." : "Supprimer définitivement"}
          </button>
        </div>
      </Modal>
    </div>
  );
}
