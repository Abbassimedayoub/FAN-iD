import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Badge, Button, Card, Input, Modal, Spinner, Table, Toast } from "./primitives";

describe("design-system primitives", () => {
  it("renders the basic form, card and table primitives", () => {
    const onClick = vi.fn();

    render(
      <>
        <Button type="button" onClick={onClick}>
          Continuer
        </Button>

        <Input aria-label="Recherche" />

        <Card>Contenu carte</Card>

        <Table aria-label="Résultats">
          <tbody>
            <tr>
              <td>Ligne</td>
            </tr>
          </tbody>
        </Table>
      </>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Continuer" }));

    expect(onClick).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Recherche")).toBeInTheDocument();
    expect(screen.getByText("Contenu carte")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Résultats" })).toBeInTheDocument();
  });

  it("renders every badge tone", () => {
    render(
      <>
        <Badge>Normal</Badge>
        <Badge tone="success">Validé</Badge>
        <Badge tone="danger">Refusé</Badge>
      </>,
    );

    expect(screen.getByText("Normal")).toBeInTheDocument();
    expect(screen.getByText("Validé")).toBeInTheDocument();
    expect(screen.getByText("Refusé")).toBeInTheDocument();
  });

  it("keeps a closed modal absent and calls onClose when opened", () => {
    const onClose = vi.fn();

    const { rerender } = render(
      <Modal open={false} onClose={onClose} title="Confirmation">
        Corps modal
      </Modal>,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    rerender(
      <Modal open onClose={onClose} title="Confirmation">
        Corps modal
      </Modal>,
    );

    expect(screen.getByRole("dialog", { name: "Confirmation" })).toBeInTheDocument();
    expect(screen.getByText("Corps modal")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Fermer" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders toast tones and spinner labels", () => {
    render(
      <>
        <Toast message="Information" />
        <Toast message="Succès" tone="success" />
        <Toast message="Erreur" tone="danger" />
        <Spinner />
        <Spinner label="Chargement personnalisé" />
      </>,
    );

    expect(screen.getByText("Information")).toBeInTheDocument();
    expect(screen.getByText("Succès")).toBeInTheDocument();
    expect(screen.getByText("Erreur")).toBeInTheDocument();
    expect(screen.getByLabelText("Chargement")).toBeInTheDocument();
    expect(screen.getByLabelText("Chargement personnalisé")).toBeInTheDocument();
  });
});
