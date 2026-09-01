#!/usr/bin/env python3
"""
Porte de non-regression de couverture, commune aux trois piles.

Source de l exigence : `FAN_id_Technical_Architecture_FR.pdf` §16.2, ligne
« Tests » — *« Pytest, Vitest, Flutter test — merge bloque si echec OU
couverture en baisse »*. La regle porte sur les TROIS executeurs, et elle
enonce une NON-REGRESSION, pas un plancher : le §17 fixe l objectif de 80 %
« concentre sur le coeur critique », explicitement pas une couverture uniforme
par pile.

Ce script ne connait donc aucun seuil. Il compare une mesure a une reference
versionnee, et rien d autre.

## Pourquoi une reference versionnee plutot qu un cache de CI

Un artefact ou un cache d execution est effacable, expire, et n apparait dans
aucun diff. Une reference qui peut disparaitre sans laisser de trace ne prouve
rien le jour ou elle manque. Le depot a deja ce motif avec `.secrets.baseline`,
que `security.yml` compare avant et apres le scan.

## Pourquoi `Decimal` et jamais `float`

Une couverture est un ratio dont l ecriture decimale n est pas representable en
binaire : `95.42` vaut en realite 95.4199999999999875... en virgule flottante.
Comparer deux mesures identiques avec `>=` finit tot ou tard par echouer sur une
difference de l ordre de 1e-13, sans qu une seule ligne ait change. `Decimal`
plus une quantification explicite en HALF_UP rendent la comparaison
deterministe et, surtout, EXPLICABLE — ce qui compte autant en soutenance qu en
production.

Le JSON est relu avec `parse_float=Decimal` : la valeur du fichier devient un
`Decimal` exact, sans jamais transiter par un `float`.

## Politique verrouillee

La politique de comparaison — metrique `line`, arrondi `HALF_UP`, 2 decimales —
est codee EN DUR ici pour qu une edition du JSON ne puisse pas l affaiblir. Le
fichier de reference doit neanmoins la declarer a l identique : toute divergence
est un `GateError`, jamais un avertissement ignore. Une politique declaree
different de la politique appliquee est le pire des deux mondes — le lecteur du
diff croit lire la regle en vigueur alors qu il lit autre chose.

## Fail-closed

Rapport absent, illisible, vide, sans compteur de lignes, pile inconnue de la
reference, reference elle-meme absente ou invalide : le script ECHOUE. Un
fichier de couverture manquant ne doit jamais se lire comme « aucune
regression » — c est precisement ainsi qu une porte de securite devient muette
tout en restant verte.

Bibliotheque standard uniquement. Aucune dependance a installer sur les
runners, y compris sur le job Flutter.
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

#: Le script vit dans `<racine>/scripts/`. La racine se deduit donc de son
#: propre emplacement, et JAMAIS du repertoire courant : `ci-web.yml` et
#: `ci-mobile.yml` declarent un `working-directory` different de la racine, et
#: une resolution par `cwd` donnerait un chemin faux selon le pipeline appelant.
#: Tous les chemins — reference, rapports, invocations `git` — partent d ici.
ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / ".coverage-baseline.json"
BASELINE_NAME = ".coverage-baseline.json"

#: Politique appliquee. Le JSON doit la declarer a l identique (cf. `check_policy`).
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
    """Echec de porte. Le message est destine au journal de CI, pas a un client."""


# ===========================================================================
# Quantification
# ===========================================================================


def quantize(value: Decimal) -> Decimal:
    """Arrondit a 2 decimales en HALF_UP — la regle inscrite dans la reference."""
    return value.quantize(QUANTUM, rounding=ROUND_HALF_UP)


def ratio_percent(covered: int, total: int) -> Decimal:
    """
    Pourcentage a partir des COMPTEURS, jamais d un pourcentage deja arrondi.

    Les trois formats exposent un pourcentage pre-calcule (`line-rate`, `pct`).
    On ne l utilise pas quand les compteurs sont disponibles : un pourcentage
    deja arrondi par l outil producteur ferait subir DEUX arrondis successifs a
    la mesure, et deux outils differents n arrondissent pas de la meme facon.
    """
    if total <= 0:
        raise GateError("rapport sans ligne mesurable (total = 0) — mesure impossible")
    if covered < 0 or covered > total:
        raise GateError(
            f"compteurs incoherents : {covered} lignes couvertes sur {total} mesurables"
        )
    return quantize(Decimal(covered) / Decimal(total) * Decimal(100))


# ===========================================================================
# Lecture et validation de la reference
# ===========================================================================


def load_baseline(text: str | None = None, origin: str | None = None) -> dict[str, Any]:
    """
    Charge ET valide la reference.

    `parse_float=Decimal` : aucune valeur ne passe par un `float`, donc aucune
    perte avant la comparaison.

    `origin` sert uniquement a nommer la source dans les messages d erreur —
    le fichier de travail, ou une revision `git`.
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
    """
    La politique declaree doit etre EXACTEMENT la politique appliquee.

    Fail-closed dans les deux sens : une valeur absente est aussi refusee qu une
    valeur divergente. On ne lit pas ces champs pour s en servir — la politique
    reste en dur — on les lit pour interdire qu ils mentent.
    """
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
    # `2` peut arriver en `int` (entier JSON) ; un `2.0` deviendrait `Decimal`.
    if not isinstance(decimals, (int, Decimal)) or isinstance(decimals, bool):
        raise GateError(f"{label} : `comparison.decimals` non numerique : {decimals!r}")
    if Decimal(decimals) != Decimal(DECIMALS):
        raise GateError(
            f"{label} : `comparison.decimals` vaut {decimals!r}, attendu {DECIMALS}."
        )


def baseline_entry(document: dict[str, Any], stack: str, label: str = BASELINE_NAME) -> dict[str, Any]:
    """Entree d une pile. Une pile absente est un ECHEC, jamais un defaut implicite."""
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
    """
    Chemin du rapport, TOUJOURS resolu depuis la racine deduite du script.

    Un chemin absolu ou remontant hors du depot est refuse : la reference
    designe des artefacts du depot, pas un fichier arbitraire du runner.
    """
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
# Lecture des rapports — un format par pile
# ===========================================================================


def measure_backend(path: Path) -> Decimal:
    """
    Cobertura produit par `coverage.py` (`pytest --cov-report=xml`).

    Les compteurs `lines-covered` / `lines-valid` sont preferes a `line-rate`,
    qui est deja arrondi par l outil.
    """
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
    """Istanbul `json-summary`, produit par `@vitest/coverage-v8`."""
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
    """
    LCOV produit par `flutter test --coverage`.

    `LF:` = lignes trouvees, `LH:` = lignes atteintes, une paire par fichier.
    On somme sur l ensemble des enregistrements : c est la seule facon
    d obtenir un pourcentage GLOBAL, un fichier a la fois n en donnant qu un
    local.
    """
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
    """Mesure la couverture courante de la pile, depuis le rapport declare."""
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
# Ecriture de la reference
# ===========================================================================


def write_baseline(document: dict[str, Any]) -> None:
    """
    Reecrit la reference.

    `float()` a l ecriture est sur ICI, et seulement ici : les valeurs sont
    quantifiees a 2 decimales, et `repr` d un tel float redonne exactement la
    meme ecriture decimale. La relecture repasse par `Decimal`.

    Consequence assumee : une valeur entiere en centiemes s ecrit `96.0` et non
    `96.00`. JSON n a pas de notation a virgule fixe, et les deux ecritures sont
    egales apres requantification. On n ajoute pas d encodeur maison pour une
    question de presentation.
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
# Commandes
# ===========================================================================


def command_check(stack: str) -> int:
    """
    La couverture courante ne doit jamais etre inferieure a la reference versionnee.

    Une hausse est acceptee : la reference versionnee reste un plancher
    conservateur et reproductible entre environnements. Cela evite qu une petite
    variation positive propre au runner GitHub Actions rende le pipeline rouge,
    tout en conservant la regle essentielle : aucune baisse sous la reference.

    Echecs possibles, tous fail-closed : reference HEAD absente ou invalide,
    politique divergente, pile absente de HEAD, rapport absent / vide /
    illisible.
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
    """
    Releve la reference a la mesure courante. REFUSE toute baisse.

    Ce refus est une commodite, pas la garantie : une edition manuelle du JSON
    contourne cette commande. La garantie est `guard-baseline`, qui s exerce
    sur le diff en CI.
    """
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
    """Invocation `git` ancree sur la racine du depot, jamais sur le cwd du job."""
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True)


def require_commit(base: str) -> None:
    """
    Le SHA de base doit designer un commit REELLEMENT present dans ce clone.

    Verifie AVANT toute autre chose : sans elle, `git show` echoue de la meme
    facon pour « commit inconnu » et pour « fichier absent », et les deux se
    confondraient en un bootstrap silencieux. Un clone superficiel neutraliserait
    alors la porte sans le moindre message.
    """
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
    """
    Reference telle qu elle existait au commit de base.

    Retourne `None` UNIQUEMENT quand le fichier n existait pas a ce commit —
    seul cas de bootstrap legitime. Tout autre echec remonte en `GateError` :
    un fichier present mais illisible, ou declarant une politique divergente,
    ne doit jamais se lire comme un fichier absent, sinon il suffirait de
    commiter un JSON casse a la base pour basculer en bootstrap.
    """
    require_commit(base)

    if _git("cat-file", "-e", f"{base}:{BASELINE_NAME}").returncode != 0:
        # Le commit existe (verifie ci-dessus) : c est bien le fichier qui manque.
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
    Detecte le cas tres precis du premier merge d une branche historique vers une
    branche dont le premier parent ne possedait pas encore cette reference.

    L exception n est valable que si :
    - `base` est un merge a exactement deux parents ;
    - le premier parent ne possedait pas la pile concernee ;
    - le second parent possedait la pile ;
    - le merge a herite EXACTEMENT de la valeur du second parent.

    Ainsi, un commit normal ulterieur ne peut jamais reutiliser ce bootstrap.
    """

    parents = _git("rev-list", "--parents", "-n", "1", base)
    if parents.returncode != 0:
        raise GateError(
            f"lecture impossible des parents du commit de base {base}: "
            f"{parents.stderr.strip() or 'erreur git non detaillee'}"
        )

    fields = parents.stdout.strip().split()

    # SHA du commit + exactement deux parents.
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
    Protege la reference versionnee contre toute baisse.

    Cas ordinaires :
    - pile deja presente a la base : HEAD >= BASE ;
    - pile nouvelle : HEAD == mesure courante.

    Cas exceptionnel de migration par merge :
    une reference heritee du second parent d un merge peut etre re-bootstrappee
    une seule fois si le premier parent ne possedait pas cette pile et si le
    merge a repris exactement la valeur du second parent.

    Pour ce bootstrap herite uniquement, une mesure courante superieure a la
    reference est acceptee : la reference reste alors conservatrice. Une reference
    superieure a la mesure reste interdite. Cette exception ne s applique jamais
    aux commits ordinaires.
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
# Entree
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