import {
  useEffect,
  useState,
} from "react";
import {
  useQuery,
} from "@tanstack/react-query";

import {
  Button,
  Card,
  Input,
  Spinner,
} from "@/components/primitives";

import {
  createTicketCategory,
  deleteTicketCategory,
  fetchTicketCategories,
  updateTicketCategory,
} from "./api";
import type {
  OrganizerEvent,
  TicketCategory,
  TicketCategoryInput,
} from "./types";

interface OrganizerEventCategoriesStepProps {
  event: OrganizerEvent;
  onBack: () => void;
  onSaveDraft?: () => void;
  onContinue: () => void;
}

function categoryErrorMessage(
  error: unknown,
): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "code" in error
  ) {
    const code = (
      error as {
        code?: unknown;
      }
    ).code;

    switch (code) {
      case "TICKET_CATEGORY_ALREADY_EXISTS":
        return "Une catégorie portant ce nom existe déjà.";
      case "TICKET_CATEGORY_HAS_SALES":
        return "Cette catégorie possède déjà des ventes et ne peut plus être supprimée.";
      case "STALE_RESOURCE":
        return "Cette catégorie a été modifiée ailleurs. Rechargez les données puis réessayez.";
      case "VALIDATION_ERROR":
        return "Les valeurs de cette catégorie ne respectent pas les règles de quotas.";
      case "NETWORK_ERROR":
        return "Connexion au serveur impossible. Réessayez.";
    }
  }

  return "Impossible d’enregistrer cette catégorie. Réessayez.";
}

function parseEuroToCents(
  value: string,
): number | null {
  const normalized = value
    .trim()
    .replace(",", ".");

  if (
    !/^\d+(?:\.\d{1,2})?$/.test(
      normalized,
    )
  ) {
    return null;
  }

  const [euros, decimals = ""] =
    normalized.split(".");

  const cents = Number(euros) * 100 +
    Number(
      decimals.padEnd(2, "0"),
    );

  if (
    !Number.isSafeInteger(cents) ||
    cents < 0
  ) {
    return null;
  }

  return cents;
}

function formatEuro(
  cents: number,
): string {
  return new Intl.NumberFormat(
    "fr-FR",
    {
      style: "currency",
      currency: "EUR",
    },
  ).format(cents / 100);
}

function TicketCategoryEditor({
  category,
  onChanged,
}: {
  category: TicketCategory;
  onChanged: () => Promise<void>;
}) {
  const [
    name,
    setName,
  ] = useState(category.name);

  const [
    quota,
    setQuota,
  ] = useState(
    String(category.quota),
  );

  const [
    price,
    setPrice,
  ] = useState(
    (
      category.unit_price_cents /
      100
    ).toFixed(2),
  );

  const [
    pending,
    setPending,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  );

  useEffect(() => {
    setName(category.name);
    setQuota(
      String(category.quota),
    );
    setPrice(
      (
        category.unit_price_cents /
        100
      ).toFixed(2),
    );
  }, [category]);

  async function save(): Promise<void> {
    setError(null);

    const parsedQuota =
      Number(quota);

    const cents =
      parseEuroToCents(price);

    if (!name.trim()) {
      setError(
        "Le nom est requis.",
      );
      return;
    }

    if (
      !Number.isInteger(
        parsedQuota,
      ) ||
      parsedQuota < 1
    ) {
      setError(
        "Le quota doit être un entier positif.",
      );
      return;
    }

    if (cents === null) {
      setError(
        "Le prix doit être un montant valide avec au maximum deux décimales.",
      );
      return;
    }

    setPending(true);

    try {
      await updateTicketCategory(
        category,
        {
          name: name.trim(),
          quota: parsedQuota,
          unit_price_cents: cents,
        },
      );

      await onChanged();
    } catch (caught) {
      setError(
        categoryErrorMessage(
          caught,
        ),
      );
    } finally {
      setPending(false);
    }
  }

  async function remove(): Promise<void> {
    setError(null);
    setPending(true);

    try {
      await deleteTicketCategory(
        category,
      );

      await onChanged();
    } catch (caught) {
      setError(
        categoryErrorMessage(
          caught,
        ),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="rounded-2xl border border-[#e2e8ee] bg-white p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-[#2e4157]">
            {category.name}
          </p>

          <p className="mt-1 text-xs text-[#8a96a4]">
            {category.sold_count} vendu
            {category.sold_count > 1
              ? "s"
              : ""}{" "}
            ·{" "}
            {category.available_count} disponible
            {category.available_count > 1
              ? "s"
              : ""}
          </p>
        </div>

        <span className="rounded-full bg-[#eef5ff] px-3 py-1 text-xs font-bold text-[#1769d2]">
          {formatEuro(
            category.unit_price_cents,
          )}
        </span>
      </div>

      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_150px_150px]">
        <div>
          <label
            htmlFor={`ticket-name-${category.id}`}
            className="mb-1.5 block text-xs font-semibold text-[#536578]"
          >
            Nom
          </label>

          <Input
            id={`ticket-name-${category.id}`}
            value={name}
            onChange={(event) => {
              setName(
                event.target.value,
              );
            }}
            className="w-full"
          />
        </div>

        <div>
          <label
            htmlFor={`ticket-quota-${category.id}`}
            className="mb-1.5 block text-xs font-semibold text-[#536578]"
          >
            Quota
          </label>

          <Input
            id={`ticket-quota-${category.id}`}
            inputMode="numeric"
            value={quota}
            onChange={(event) => {
              setQuota(
                event.target.value,
              );
            }}
            className="w-full"
          />
        </div>

        <div>
          <label
            htmlFor={`ticket-price-${category.id}`}
            className="mb-1.5 block text-xs font-semibold text-[#536578]"
          >
            Prix (€)
          </label>

          <Input
            id={`ticket-price-${category.id}`}
            inputMode="decimal"
            value={price}
            onChange={(event) => {
              setPrice(
                event.target.value,
              );
            }}
            className="w-full"
          />
        </div>
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-3 text-xs font-medium text-red-600"
        >
          {error}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <Button
          type="button"
          disabled={pending}
          onClick={() => {
            void remove();
          }}
          className="border border-red-200 bg-white px-4 text-red-700 hover:bg-red-50"
        >
          Supprimer
        </Button>

        <Button
          type="button"
          disabled={pending}
          onClick={() => {
            void save();
          }}
          className="bg-[#1769d2] px-4 font-semibold hover:bg-[#125bb9]"
        >
          {pending
            ? "Enregistrement…"
            : "Enregistrer"}
        </Button>
      </div>
    </div>
  );
}

export function OrganizerEventCategoriesStep({
  event,
  onBack,
  onSaveDraft,
  onContinue,
}: OrganizerEventCategoriesStepProps) {
  const [
    name,
    setName,
  ] = useState("");

  const [
    quota,
    setQuota,
  ] = useState("");

  const [
    price,
    setPrice,
  ] = useState("");

  const [
    mutationPending,
    setMutationPending,
  ] = useState(false);

  const [
    mutationError,
    setMutationError,
  ] = useState<string | null>(
    null,
  );

  const query = useQuery({
    queryKey: [
      "catalog",
      "event",
      event.id,
      "ticket-categories",
    ],
    queryFn: () =>
      fetchTicketCategories(
        event.id,
      ),
  });

  const categories =
    query.data ?? [];

  const allocatedQuota =
    categories.reduce(
      (
        total,
        category,
      ) =>
        total +
        category.quota,
      0,
    );

  const remainingCapacity =
    event.capacity_total === null
      ? null
      : event.capacity_total -
        allocatedQuota;

  async function refresh(): Promise<void> {
    await query.refetch();
  }

  async function create(): Promise<void> {
    setMutationError(null);

    if (
      event.capacity_total === null
    ) {
      setMutationError(
        "Définissez d’abord la capacité totale de l’événement.",
      );
      return;
    }

    const parsedQuota =
      Number(quota);

    const cents =
      parseEuroToCents(price);

    if (!name.trim()) {
      setMutationError(
        "Le nom de la catégorie est requis.",
      );
      return;
    }

    if (
      !Number.isInteger(
        parsedQuota,
      ) ||
      parsedQuota < 1
    ) {
      setMutationError(
        "Le quota doit être un entier positif.",
      );
      return;
    }

    if (cents === null) {
      setMutationError(
        "Le prix doit être un montant valide avec au maximum deux décimales.",
      );
      return;
    }

    if (
      allocatedQuota +
        parsedQuota >
      event.capacity_total
    ) {
      setMutationError(
        "Le total des quotas ne peut pas dépasser la capacité de l’événement.",
      );
      return;
    }

    const input: TicketCategoryInput = {
      name: name.trim(),
      quota: parsedQuota,
      unit_price_cents: cents,
    };

    setMutationPending(true);

    try {
      await createTicketCategory(
        event.id,
        input,
      );

      setName("");
      setQuota("");
      setPrice("");

      await refresh();
    } catch (caught) {
      setMutationError(
        categoryErrorMessage(
          caught,
        ),
      );
    } finally {
      setMutationPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden border-[#e1e7ed] p-0 shadow-[0_10px_28px_rgba(23,45,74,0.05)]">
        <div className="border-b border-[#edf0f3] px-6 py-5 sm:px-8">
          <h2 className="font-sora text-lg font-bold text-[#26384f]">
            Catégories & quotas
          </h2>

          <p className="mt-1 text-sm text-[#8591a0]">
            Définissez les zones de vente, leurs quotas et leurs prix.
          </p>
        </div>

        <div className="grid gap-3 bg-[#fbfcfd] p-5 sm:grid-cols-3 sm:p-6">
          <div className="rounded-xl border border-[#e3e9ef] bg-white px-4 py-4">
            <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#929daa]">
              Capacité totale
            </p>

            <p className="mt-2 text-xl font-bold text-[#30445b]">
              {event.capacity_total ??
                "À définir"}
            </p>
          </div>

          <div className="rounded-xl border border-[#e3e9ef] bg-white px-4 py-4">
            <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#929daa]">
              Quotas alloués
            </p>

            <p className="mt-2 text-xl font-bold text-[#30445b]">
              {allocatedQuota}
            </p>
          </div>

          <div className="rounded-xl border border-[#cfe2fb] bg-[#f5f9ff] px-4 py-4">
            <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#7291b5]">
              Places restantes
            </p>

            <p className="mt-2 text-xl font-bold text-[#1769d2]">
              {remainingCapacity ??
                "—"}
            </p>
          </div>
        </div>
      </Card>

      <Card className="border-[#e1e7ed] p-6 shadow-[0_10px_28px_rgba(23,45,74,0.04)] sm:p-7">
        <div className="mb-5">
          <h3 className="font-sora text-base font-bold text-[#30445b]">
            Ajouter une catégorie
          </h3>

          <p className="mt-1 text-xs leading-5 text-[#8a96a4]">
            Exemple : Tribune Honneur, Virage Nord ou Zone VIP.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_160px_160px]">
          <div>
            <label
              htmlFor="new-ticket-category-name"
              className="mb-2 block text-[13px] font-semibold text-[#40556b]"
            >
              Nom de la catégorie de billets
            </label>

            <Input
              id="new-ticket-category-name"
              value={name}
              onChange={(event) => {
                setName(
                  event.target.value,
                );
              }}
              placeholder="Ex. Tribune Honneur"
              className="w-full"
            />
          </div>

          <div>
            <label
              htmlFor="new-ticket-category-quota"
              className="mb-2 block text-[13px] font-semibold text-[#40556b]"
            >
              Quota
            </label>

            <Input
              id="new-ticket-category-quota"
              inputMode="numeric"
              value={quota}
              onChange={(event) => {
                setQuota(
                  event.target.value,
                );
              }}
              placeholder="1000"
              className="w-full"
            />
          </div>

          <div>
            <label
              htmlFor="new-ticket-category-price"
              className="mb-2 block text-[13px] font-semibold text-[#40556b]"
            >
              Prix unitaire (€)
            </label>

            <Input
              id="new-ticket-category-price"
              inputMode="decimal"
              value={price}
              onChange={(event) => {
                setPrice(
                  event.target.value,
                );
              }}
              placeholder="25,00"
              className="w-full"
            />
          </div>
        </div>

        {mutationError ? (
          <p
            role="alert"
            className="mt-4 text-sm font-medium text-red-600"
          >
            {mutationError}
          </p>
        ) : null}

        <div className="mt-5 flex justify-end">
          <Button
            type="button"
            disabled={
              mutationPending ||
              event.capacity_total ===
                null
            }
            onClick={() => {
              void create();
            }}
            className="bg-[#1769d2] px-5 font-semibold hover:bg-[#125bb9]"
          >
            {mutationPending
              ? "Ajout…"
              : "Ajouter la catégorie"}
          </Button>
        </div>
      </Card>

      <Card className="overflow-hidden border-[#e1e7ed] p-0 shadow-[0_10px_28px_rgba(23,45,74,0.04)]">
        <div className="flex items-center justify-between gap-4 border-b border-[#edf0f3] px-6 py-5 sm:px-8">
          <div>
            <h3 className="font-sora text-base font-bold text-[#30445b]">
              Catégories configurées
            </h3>

            <p className="mt-1 text-xs text-[#8a96a4]">
              {categories.length} catégorie
              {categories.length > 1
                ? "s"
                : ""}
            </p>
          </div>
        </div>

        <div className="p-5 sm:p-6">
          {query.isPending ? (
            <div className="flex min-h-[120px] items-center justify-center">
              <Spinner label="Chargement des catégories de billets" />
            </div>
          ) : query.isError ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">
              Impossible de charger les catégories de billets.
            </div>
          ) : categories.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#d8e0e8] bg-[#fbfcfd] px-5 py-8 text-center">
              <p className="text-sm font-semibold text-[#526478]">
                Aucune catégorie pour le moment
              </p>

              <p className="mt-1 text-xs text-[#909ba8]">
                Ajoutez au moins une catégorie avant de publier l’événement.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {categories.map(
                (category) => (
                  <TicketCategoryEditor
                    key={category.id}
                    category={category}
                    onChanged={
                      refresh
                    }
                  />
                ),
              )}
            </div>
          )}
        </div>
      </Card>

      <div className="border-t border-[#e4e9ee] pt-5">
        <div className="mb-4 rounded-xl border border-[#dbe7f4] bg-[#f7faff] px-4 py-3">
          <p className="text-xs leading-5 text-[#61778e]">
            Les catégories ajoutées ou modifiées sont enregistrées
            immédiatement dans le brouillon. Vous pouvez quitter maintenant
            et reprendre la création plus tard.
          </p>
        </div>

        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Button
            type="button"
            onClick={onBack}
            className="border border-[#ccd6e0] bg-white px-5 font-semibold text-[#536578] hover:bg-[#f7f9fb]"
          >
            ← Retour aux informations
          </Button>

          <div className="flex flex-col gap-3 sm:flex-row">
            {onSaveDraft ? (
              <Button
                type="button"
                disabled={mutationPending}
                onClick={onSaveDraft}
                className="border border-[#b9cbe0] bg-white px-5 font-semibold text-[#405b78] hover:bg-[#f5f8fc]"
              >
                Enregistrer le brouillon et quitter
              </Button>
            ) : null}

            <Button
              type="button"
              disabled={
                mutationPending ||
                categories.length === 0
              }
              onClick={onContinue}
              title={
                categories.length === 0
                  ? "Ajoutez au moins une catégorie."
                  : undefined
              }
              className="min-w-[220px] bg-[#1769d2] px-5 font-semibold shadow-[0_8px_20px_rgba(23,105,210,0.18)]"
            >
              Continuer vers la publication
              <span
                aria-hidden="true"
                className="ml-2"
              >
                →
              </span>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
