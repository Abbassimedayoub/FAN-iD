#!/usr/bin/env python3
"""
Static consistency check between handwritten migrations and the models they are
expected to represent, without importing Django.

This does not replace `makemigrations --check --dry-run`; it is an additional
offline safety net that compares model and migration fields through AST analysis
without executing project code.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _field_names_from_class(class_node: ast.ClassDef) -> set[str]:
    names = set()
    for node in class_node.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
            if target.startswith("_") or target in {"Meta"}:
                continue
            # Keep only assignments that look like Django model fields.
            # (appel de fonction, ex. models.CharField(...), TextChoices exclu).
            if isinstance(node.value, ast.Call):
                callee = node.value.func
                callee_name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", "")
                # `objects = UserManager()` is not a field; managers and querysets are class
                # attributes and therefore absent from migrations.
                if callee_name.endswith(("Manager", "QuerySet")) or callee_name in {
                    "as_manager",
                    "from_queryset",
                }:
                    continue
                names.add(target)
    return names


def extract_model_fields(models_path: Path) -> dict[str, set[str]]:
    tree = ast.parse(models_path.read_text(encoding="utf-8"))
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
            (isinstance(base, ast.Attribute) and base.attr == "Model")
            or (
                isinstance(base, ast.Name)
                and base.id
                in {
                    "Model",
                    "AbstractUser",
                    "UUIDModel",
                    "TimeStampedModel",
                    "VersionedModel",
                }
            )
            for base in node.bases
        ):
            result[node.name] = _field_names_from_class(node)
    return result


def extract_migration_fields(migration_path: Path) -> dict[str, set[str]]:
    """Fields declared by both CreateModel and AddField operations in a migration file."""
    tree = ast.parse(migration_path.read_text(encoding="utf-8"))
    result: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "CreateModel"
        ):
            model_name = None
            fields_arg = None
            for kw in node.keywords:
                if kw.arg == "name":
                    model_name = kw.value.value if isinstance(kw.value, ast.Constant) else None
                if kw.arg == "fields":
                    fields_arg = kw.value
            if model_name is None or fields_arg is None or not isinstance(fields_arg, ast.List):
                continue
            names = set()
            for element in fields_arg.elts:
                if isinstance(element, ast.Tuple) and len(element.elts) >= 1:
                    first = element.elts[0]
                    if isinstance(first, ast.Constant):
                        names.add(first.value)
            result[model_name] = names

        # AddField stores model_name in lowercase, so comparison normalizes the name.
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "AddField"
        ):
            model_name = None
            field_name = None
            for kw in node.keywords:
                if kw.arg == "model_name" and isinstance(kw.value, ast.Constant):
                    model_name = str(kw.value.value)
                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                    field_name = str(kw.value.value)
            if model_name and field_name:
                result.setdefault(model_name, set()).add(field_name)
    return result


# One model may span several migrations, so compare against the union of their fields.
CHECKS = [
    (
        BACKEND_DIR / "apps/identity/models.py",
        # Discover all app migrations automatically instead of maintaining a manual file list.
        sorted((BACKEND_DIR / "apps/identity/migrations").glob("0*.py")),
        {
            "User": "User",
            "Role": "Role",
            "Device": "Device",
            "Session": "Session",
            "MfaChallenge": "MfaChallenge",
        },
    ),
    (
        BACKEND_DIR / "apps/core/idempotency/models.py",
        BACKEND_DIR / "apps/core/migrations/0001_infrastructure.py",
        {"IdempotencyRecord": "IdempotencyRecord"},
    ),
    (
        BACKEND_DIR / "apps/core/outbox/models.py",
        BACKEND_DIR / "apps/core/migrations/0001_infrastructure.py",
        {"OutboxEvent": "OutboxEvent", "ConsumedEvent": "ConsumedEvent"},
    ),
]

# Fields inherited from AbstractUser are not redeclared in identity.User but must still exist in migrations.
IMPLICIT_PK_FIELDS: dict[str, set[str]] = {
    # UUIDModel is abstract and contributes the id field to subclasses.
    "Device": {"id"},
    "Session": {"id"},
    "MfaChallenge": {"id"},
    # Models whose class body declares no primary key
    # explicite : Django ajoute alors implicitement un "id" (BigAutoField,
    # use DEFAULT_AUTO_FIELD from settings/base.py, which therefore appears in
    # the migration without a corresponding assignment in models.py.
    "ConsumedEvent": {"id"},
}

# Fields contributed by core mixins (`TimeStampedModel`,
# `VersionedModel`) or AbstractUser and absent from the class body.
INHERITED_FIELDS = {
    "User": {
        "created_at",
        "updated_at",
        "version",
        "password",
        "last_login",
        "is_superuser",
        "username",
        "first_name",
        "last_name",
        "email",
        "is_staff",
        "is_active",
        "date_joined",
        "groups",
        "user_permissions",
    }
}


def main() -> int:
    exit_code = 0
    for models_path, migration_paths, mapping in CHECKS:
        if isinstance(migration_paths, Path):
            migration_paths = [migration_paths]
        model_fields = extract_model_fields(models_path)
        migration_fields: dict[str, set[str]] = {}
        for migration_path in migration_paths:
            for key, value in extract_migration_fields(migration_path).items():
                migration_fields.setdefault(key.lower(), set()).update(value)

        for model_name, migration_model_name in mapping.items():
            declared = model_fields.get(model_name, set())
            inherited = INHERITED_FIELDS.get(model_name, set())
            implicit_pk = IMPLICIT_PK_FIELDS.get(model_name, set())
            expected = declared | inherited | implicit_pk
            actual = migration_fields.get(migration_model_name.lower(), set())

            missing_in_migration = expected - actual
            extra_in_migration = actual - expected

            status = "OK" if not missing_in_migration and not extra_in_migration else "MISMATCH"
            sources = ", ".join(p.name for p in migration_paths)
            print(f"[{status}] {model_name} ({models_path.relative_to(BACKEND_DIR)} vs {sources})")
            if missing_in_migration:
                print(f"    manquant dans la migration : {sorted(missing_in_migration)}")
                exit_code = 1
            if extra_in_migration:
                print(f"    en trop dans la migration   : {sorted(extra_in_migration)}")
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
