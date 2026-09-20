#!/usr/bin/env python3
"""
Coverage non-regression gate shared by all supported application stacks.

The script compares current line coverage against a versioned baseline. It does
not define a universal coverage threshold; its purpose is to prevent an
unreviewed decrease from the committed reference.

A versioned baseline is used instead of an ephemeral CI cache so every change is
visible in repository history. Coverage values use `Decimal`, never binary
floating point, and are quantized with an explicit HALF_UP policy for
deterministic comparisons.

The comparison policy is hard-coded here and must match the metadata declared by
the baseline file. Missing or malformed reports, unknown stacks, invalid
baselines, and policy mismatches all fail closed.

The implementation uses only the Python standard library so every CI runner can
execute the same gate without installing another dependency.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

#: The script lives under `<root>/scripts/`, so repository paths are resolved from
#: this file's location rather than the caller's working directory.
ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / ".coverage-baseline.json"
BASELINE_NAME = ".coverage-baseline.json"

#: Applied comparison policy. The JSON baseline must declare the same values.
METRIC = "line"
ROUNDING_NAME = "HALF_UP"
DECIMALS = 2
QUANTUM = Decimal("0.01")

EXPECTED_REPORTS = {
    "backend": "backend/coverage.xml",
    "web": "web/coverage/coverage-summary.json",
    "mobile": "mobile/coverage/lcov.info",
}


class GateError(Exception):
    """Coverage-gate failure intended for CI logs rather than an end user."""


# ===========================================================================
# Quantization
# ===========================================================================


def quantize(value: Decimal) -> Decimal:
    """Round to two decimal places with HALF_UP, matching the baseline policy."""
    return value.quantize(QUANTUM, rounding=ROUND_HALF_UP)


def ratio_percent(covered: int, total: int) -> Decimal:
    """
    Compute coverage percentage from counters instead of an already-rounded
    percentage exposed by the producing tool, avoiding double rounding.
    """
    if total <= 0:
        raise GateError("rapport sans ligne mesurable (total = 0) — mesure impossible")
    if covered < 0 or covered > total:
        raise GateError(
            f"compteurs incoherents : {covered} lignes couvertes sur {total} mesurables"
        )
    return quantize(Decimal(covered) / Decimal(total) * Decimal(100))


# ===========================================================================
# Baseline loading and validation
# ===========================================================================


def load_baseline(text: str | None = None, origin: str | None = None) -> dict[str, Any]:
    """
    Load and validate a baseline.

    `parse_float=Decimal` avoids precision loss before comparison. `origin`
    is used only to name the source in diagnostics.
    """
    label = origin or BASELINE_NAME
    if text is None:
        if not BASELINE_PATH.is_file():
            raise GateError(
                f"{BASELINE_NAME} introuvable a la racine du depot ({ROOT}).\n"
                "  La porte ECHOUE : sans reference, il n existe rien a comparer."
            )
        text = BASELINE_PATH.read_text(encoding="utf-8")

    try:
        document = json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise GateError(f"{label} illisible : {exc}") from exc

    if not isinstance(document, dict):
        raise GateError(f"{label} : objet JSON attendu a la racine")

    check_policy(document, label)
    return document


def check_policy(document: dict[str, Any], label: str) -> None:
    """The declared policy must exactly match the hard-coded applied policy; missing or divergent values fail closed."""
    metric = document.get("metric")
    if metric != METRIC:
        raise GateError(
            f"{label} : `metric` vaut {metric!r}, attendu {METRIC!r}.\n"
            "  La politique de comparaison est verrouillee dans le script ; "
            "une declaration divergente serait trompeuse."
        )

    comparison = document.get("comparison")
    if not isinstance(comparison, dict):
        raise GateError(f"{label} : bloc `comparison` absent ou mal forme")

    rounding = comparison.get("rounding")
    if rounding != ROUNDING_NAME:
        raise GateError(
            f"{label} : `comparison.rounding` vaut {rounding!r}, attendu "
            f"{ROUNDING_NAME!r}."
        )

    decimals = comparison.get("decimals")
    # JSON may parse `2` as int while `2.0` becomes Decimal.
    if not isinstance(decimals, (int, Decimal)) or isinstance(decimals, bool):
        raise GateError(f"{label} : `comparison.decimals` non numerique : {decimals!r}")
    if Decimal(decimals) != Decimal(DECIMALS):
        raise GateError(
            f"{label} : `comparison.decimals` vaut {decimals!r}, attendu {DECIMALS}."
        )


def baseline_entry(document: dict[str, Any], stack: str, label: str = BASELINE_NAME) -> dict[str, Any]:
    """Return one stack entry; a missing stack is an error, never an implicit default."""
    stacks = document.get("stacks")
    if not isinstance(stacks, dict):
        raise GateError(f"{label} : bloc `stacks` absent ou mal forme")
    if stack not in stacks:
        raise GateError(
            f"{label} : pile {stack!r} absente de la reference.\n"
            "  La porte ECHOUE : une pile sans reference ne peut pas etre "
            "declaree non regressive."
        )
    entry = stacks[stack]
    if not isinstance(entry, dict) or "percent" not in entry or "report" not in entry:
        raise GateError(
            f"{label} : entree incomplete pour la pile {stack!r} "
            "(`percent` et `report` attendus)"
        )
    return entry


def baseline_percent(document: dict[str, Any], stack: str, label: str = BASELINE_NAME) -> Decimal:
    raw = baseline_entry(document, stack, label)["percent"]
    if isinstance(raw, bool) or not isinstance(raw, (int, Decimal)):
        raise GateError(f"{label} : `percent` non numerique pour {stack!r} : {raw!r}")
    try:
        value = quantize(Decimal(raw))
    except (InvalidOperation, TypeError) as exc:
        raise GateError(f"{label} : valeur de reference invalide pour {stack!r} : {raw!r}") from exc
    if value < 0 or value > 100:
        raise GateError(f"{label} : `percent` hors bornes pour {stack!r} : {value}")
    return value


def baseline_report(document: dict[str, Any], stack: str) -> Path:
    """Resolve the report path from repository root and reject absolute or escaping paths."""
    raw = baseline_entry(document, stack)["report"]
    if not isinstance(raw, str) or not raw.strip():
        raise GateError(f"{BASELINE_NAME} : `report` vide ou non textuel pour {stack!r}")

    expected = EXPECTED_REPORTS.get(stack)
    if expected is None:
        raise GateError(f"pile non supportee : {stack!r}")
    if raw != expected:
        raise GateError(
            f"{BASELINE_NAME} : `report` vaut {raw!r} pour {stack!r}, "
            f"attendu {expected!r}.\n"
            "  Le chemin du rapport fait partie de la politique verrouillee et "
            "ne peut pas etre redirige par la reference."
        )

    candidate = Path(raw)
    if candidate.is_absolute():
        raise GateError(f"{BASELINE_NAME} : `report` doit etre relatif a la racine : {raw!r}")
    resolved = (ROOT / candidate).resolve()
    if ROOT not in resolved.parents and resolved != ROOT:
        raise GateError(f"{BASELINE_NAME} : `report` sort du depot : {raw!r}")
    return resolved


# ===========================================================================
# Coverage report readers — one format per stack
# ===========================================================================


def measure_backend(path: Path) -> Decimal:
    """Read Cobertura XML from coverage.py, preferring raw line counters over the pre-rounded rate."""
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise GateError(f"{path} : XML illisible ({exc})") from exc

    covered = root.get("lines-covered")
    valid = root.get("lines-valid")
    if covered is not None and valid is not None:
        try:
            return ratio_percent(int(covered), int(valid))
        except ValueError as exc:
            raise GateError(f"{path} : compteurs de lignes non entiers ({exc})") from exc

    rate = root.get("line-rate")
    if rate is None:
        raise GateError(f"{path} : ni compteurs de lignes ni `line-rate`")
    try:
        return quantize(Decimal(rate) * Decimal(100))
    except InvalidOperation as exc:
        raise GateError(f"{path} : `line-rate` non numerique : {rate!r}") from exc


def measure_web(path: Path) -> Decimal:
    """Read Istanbul json-summary output produced by @vitest/coverage-v8."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise GateError(f"{path} : JSON illisible ({exc})") from exc

    if not isinstance(document, dict):
        raise GateError(f"{path} : objet JSON attendu a la racine")
    total = document.get("total")
    if not isinstance(total, dict):
        raise GateError(f"{path} : bloc `total` absent — reporter `json-summary` requis")
    lines = total.get("lines")
    if not isinstance(lines, dict) or "covered" not in lines or "total" not in lines:
        raise GateError(f"{path} : `total.lines.covered` / `total.lines.total` absents")

    covered = lines["covered"]
    count = lines["total"]
    if (
        isinstance(covered, bool)
        or not isinstance(covered, int)
        or isinstance(count, bool)
        or not isinstance(count, int)
    ):
        raise GateError(
            f"{path} : compteurs `total.lines` non entiers "
            f"(covered={covered!r}, total={count!r})"
        )

    return ratio_percent(covered, count)


def measure_mobile(path: Path) -> Decimal:
    """Read LCOV from Flutter tests and aggregate LF/LH counters globally across files."""
    found = 0
    hit = 0
    seen = False
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise GateError(f"{path} : LCOV illisible ({exc})") from exc

    for number, line in enumerate(content.splitlines(), start=1):
        try:
            if line.startswith("LF:"):
                found += int(line[3:])
                seen = True
            elif line.startswith("LH:"):
                hit += int(line[3:])
                seen = True
        except ValueError as exc:
            raise GateError(f"{path}:{number} : compteur LCOV non entier ({line!r})") from exc

    if not seen:
        raise GateError(f"{path} : aucun enregistrement LF:/LH: — rapport vide ou tronque")
    return ratio_percent(hit, found)


MEASURERS = {
    "backend": measure_backend,
    "web": measure_web,
    "mobile": measure_mobile,
}


def measure(document: dict[str, Any], stack: str) -> Decimal:
    """Measure current coverage for a stack from its declared report."""
    if stack not in MEASURERS:
        raise GateError(f"pile non supportee : {stack!r}")
    report = baseline_report(document, stack)
    if not report.is_file():
        raise GateError(
            f"rapport de couverture absent : {report}\n"
            "  La porte ECHOUE plutot que de conclure a l absence de regression."
        )
    if report.stat().st_size == 0:
        raise GateError(
            f"rapport de couverture vide : {report}\n"
            "  Un rapport de taille nulle signale un executeur qui n a rien "
            "produit, pas une couverture inchangee."
        )
    return MEASURERS[stack](report)


# ===========================================================================
# Baseline writing
# ===========================================================================


def write_baseline(document: dict[str, Any]) -> None:
    """
    Rewrite the baseline.

    Conversion to float happens only at JSON serialization after values have
    already been quantized to two decimals; loading converts them back through
    Decimal.
    """

    def encode(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {key: encode(item) for key, item in value.items()}
        if isinstance(value, list):
            return [encode(item) for item in value]
        return value

    BASELINE_PATH.write_text(
        json.dumps(encode(document), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ===========================================================================
# Commands
# ===========================================================================


def command_check(stack: str) -> int:
    """
    Require current coverage to remain at or above the versioned baseline.

    Increases are accepted while missing/invalid baselines, policy divergence,
    unknown stacks, and unreadable reports all fail closed.
    """
    document = load_baseline()
    reference = baseline_percent(document, stack)
    current = measure(document, stack)
    delta = current - reference

    print(f"[{stack}] reference={reference}%  mesure={current}%  delta={delta:+}")

    if current < reference:
        print(
            f"ECHEC — la couverture {stack} a baisse de {-delta} point(s).\n"
            "  Regle : §16.2 du dossier d architecture, « merge bloque si "
            "couverture en baisse ».",
            file=sys.stderr,
        )
        return 1

    if current > reference:
        print(
            f"[{stack}] hausse de couverture acceptee : +{delta} point(s). "
            "La reference versionnee reste le plancher de non-regression."
        )

    return 0

def command_bump(stack: str) -> int:
    """Raise the baseline to current coverage while refusing any decrease."""
    document = load_baseline()
    reference = baseline_percent(document, stack)
    current = measure(document, stack)

    if current < reference:
        print(
            f"REFUS — {stack} : {current}% est inferieur a la reference {reference}%.\n"
            "  Une reference ne descend pas. Aucun champ de justification n est "
            "prevu pour contourner cette regle.",
            file=sys.stderr,
        )
        return 1
    if current == reference:
        print(f"[{stack}] reference inchangee ({reference}%)")
        return 0

    document["stacks"][stack]["percent"] = current
    write_baseline(document)
    print(f"[{stack}] reference relevee : {reference}% -> {current}%")
    return 0


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run git commands from repository root rather than the CI job's current directory."""
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True)


def require_commit(base: str) -> None:
    """Require the base SHA to identify a commit actually present in the clone before inspecting baseline history."""
    if not base or not base.strip():
        raise GateError("--base vide : aucun commit de comparaison fourni")
    if _git("cat-file", "-e", f"{base}^{{commit}}").returncode != 0:
        raise GateError(
            f"commit de base introuvable ou invalide : {base}\n"
            "  Causes usuelles : SHA errone, ou clone superficiel. Utiliser "
            "`fetch-depth: 0` sur `actions/checkout`.\n"
            "  La porte ECHOUE : un commit de base illisible n est pas une "
            "absence de regression."
        )


def read_baseline_at(base: str) -> dict[str, Any] | None:
    """Load the baseline as it existed at the base commit; return None only when the file genuinely did not exist there."""
    require_commit(base)

    if _git("cat-file", "-e", f"{base}:{BASELINE_NAME}").returncode != 0:
        # The commit exists, so this branch means the baseline file itself is missing.
        return None

    shown = _git("show", f"{base}:{BASELINE_NAME}")
    if shown.returncode != 0:
        raise GateError(
            f"lecture impossible de {BASELINE_NAME} au commit {base} : "
            f"{shown.stderr.strip() or 'erreur git non detaillee'}"
        )
    try:
        return load_baseline(shown.stdout, origin=f"{BASELINE_NAME}@{base}")
    except GateError as exc:
        raise GateError(
            f"{BASELINE_NAME} present au commit {base} mais INVALIDE : {exc}\n"
            "  Un fichier de reference corrompu n est pas un fichier absent : "
            "la porte echoue au lieu de basculer en bootstrap."
        ) from exc


def inherited_merge_bootstrap_origin(base: str, stack: str) -> str | None:
    """
    Detect the one-time migration case where a merge inherited a stack baseline
    from its second parent while the first parent did not yet contain that stack.
    """

    parents = _git("rev-list", "--parents", "-n", "1", base)
    if parents.returncode != 0:
        raise GateError(
            f"lecture impossible des parents du commit de base {base}: "
            f"{parents.stderr.strip() or 'erreur git non detaillee'}"
        )

    fields = parents.stdout.strip().split()

    # Commit SHA plus exactly two parents.
    if len(fields) != 3:
        return None

    _, first_parent, second_parent = fields

    first = read_baseline_at(first_parent)
    second = read_baseline_at(second_parent)
    base_document = read_baseline_at(base)

    if second is None or base_document is None:
        return None

    first_stacks = (
        first.get("stacks")
        if isinstance(first, dict)
        else None
    )
    second_stacks = second.get("stacks")

    if isinstance(first_stacks, dict) and stack in first_stacks:
        return None

    if not isinstance(second_stacks, dict) or stack not in second_stacks:
        return None

    inherited = baseline_percent(
        second,
        stack,
        label=f"{BASELINE_NAME}@{second_parent}",
    )
    merged = baseline_percent(
        base_document,
        stack,
        label=f"{BASELINE_NAME}@{base}",
    )

    if merged != inherited:
        return None

    return (
        f"reference {stack!r} heritee du second parent {second_parent} "
        f"par le merge {base}, alors que le premier parent "
        f"{first_parent} ne possedait pas cette pile"
    )


def command_guard_baseline(stack: str, base: str) -> int:
    """
    Protect the versioned baseline from decreases.

    Existing stacks require HEAD >= BASE. New stacks must bootstrap from current
    measured coverage. A narrowly validated merge-migration case may inherit a
    conservative second-parent baseline once.
    """

    head = load_baseline()
    head_value = baseline_percent(head, stack)
    previous = read_baseline_at(base)

    inherited_origin = inherited_merge_bootstrap_origin(base, stack)

    if previous is None:
        origin = f"{BASELINE_NAME} absent du commit {base}"
        inherited_origin = None

    elif (
        not isinstance(previous.get("stacks"), dict)
        or stack not in previous["stacks"]
    ):
        origin = f"pile {stack!r} absente de {BASELINE_NAME} au commit {base}"
        inherited_origin = None

    elif inherited_origin is not None:
        origin = inherited_origin

    else:
        base_value = baseline_percent(
            previous,
            stack,
            label=f"{BASELINE_NAME}@{base}",
        )

        print(
            f"[{stack}] reference base={base_value}%  "
            f"HEAD={head_value}%"
        )

        if head_value < base_value:
            print(
                f"ECHEC — la reference {stack} a ete ABAISSEE : "
                f"{base_value}% -> {head_value}%.\n"
                "  Une reference versionnee ne diminue jamais.",
                file=sys.stderr,
            )
            return 1

        return 0

    current = measure(head, stack)

    print(
        f"[{stack}] bootstrap ({origin}) : "
        f"HEAD={head_value}%  mesure={current}%"
    )

    if inherited_origin is None:
        if head_value != current:
            print(
                f"ECHEC — reference introduite a {head_value}% alors que "
                f"la mesure vaut {current}%.\n"
                "  Une reference nouvelle doit valoir exactement la "
                "couverture constatee.",
                file=sys.stderr,
            )
            return 1

        return 0

    if head_value > current:
        print(
            f"ECHEC — reference de bootstrap {head_value}% superieure "
            f"a la mesure {current}%.",
            file=sys.stderr,
        )
        return 1

    drift = current - head_value

    if drift:
        print(
            f"[{stack}] mesure superieure a la reference de bootstrap : "
            f"+{drift} point(s). Reference conservatrice acceptee uniquement "
            "pour ce bootstrap de merge."
        )

    return 0


# ===========================================================================
# Entry point
# ===========================================================================


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("check", "bump"):
        item = sub.add_parser(name)
        item.add_argument("--stack", required=True, choices=sorted(MEASURERS))

    guard = sub.add_parser("guard-baseline")
    guard.add_argument("--stack", required=True, choices=sorted(MEASURERS))
    guard.add_argument("--base", required=True, help="SHA du commit de comparaison")

    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            return command_check(args.stack)
        if args.command == "bump":
            return command_bump(args.stack)
        return command_guard_baseline(args.stack, args.base)
    except GateError as error:
        print(f"ECHEC — {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())