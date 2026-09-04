import {
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import {
  beforeEach,
  describe,
  expect,
  it,
} from "vitest";

import { LanguageSwitcher } from "./LanguageSwitcher";
import { LANGUAGE_STORAGE_KEY } from "./language";

describe("LanguageSwitcher", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.lang = "";
  });

  it("affiche les vrais drapeaux France et Royaume-Uni", () => {
    render(<LanguageSwitcher />);

    expect(
      screen.getByTestId("flag-fr"),
    ).toBeInTheDocument();

    expect(
      screen.getByTestId("flag-en"),
    ).toBeInTheDocument();

    expect(
      screen.queryByText("FR"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("EN"),
    ).not.toBeInTheDocument();
  });

  it("utilise le français par défaut", () => {
    render(<LanguageSwitcher />);

    expect(
      screen.getByRole("button", {
        name: "Français",
      }),
    ).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    expect(
      document.documentElement.lang,
    ).toBe("fr");
  });

  it("persiste la langue anglaise", () => {
    render(<LanguageSwitcher />);

    fireEvent.click(
      screen.getByRole("button", {
        name: "English",
      }),
    );

    expect(
      window.localStorage.getItem(
        LANGUAGE_STORAGE_KEY,
      ),
    ).toBe("en");

    expect(
      document.documentElement.lang,
    ).toBe("en");
  });
});
