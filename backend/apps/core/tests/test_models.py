"""Tests unitaires des modèles de base (§55 master prompt)."""

import uuid

from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel, VersionedModel


# Modèles concrets de test — jamais migrés en production, utilisés uniquement
# pour exercer les classes abstraites du socle.
class _DummyUUIDModel(UUIDModel):
    class Meta:
        app_label = "core"
        managed = False


class _DummyTimeStampedModel(TimeStampedModel):
    class Meta:
        app_label = "core"
        managed = False


class _DummyVersionedModel(VersionedModel):
    name = models.CharField(max_length=50, default="x")

    class Meta:
        app_label = "core"
        managed = False


def test_uuid_model_generates_uuid4_pk():
    instance = _DummyUUIDModel()
    assert isinstance(instance.id, uuid.UUID)
    assert instance.id.version == 4


def test_uuid_model_pk_is_not_editable():
    field = _DummyUUIDModel._meta.get_field("id")
    assert field.editable is False


def test_timestamped_model_has_created_and_updated_fields():
    fields = {f.name for f in _DummyTimeStampedModel._meta.get_fields()}
    assert {"created_at", "updated_at"}.issubset(fields)


def test_versioned_model_default_version_is_one():
    instance = _DummyVersionedModel()
    assert instance.version == 1


def test_versioned_model_save_uses_f_expression_when_updating():
    # `_DummyVersionedModel` n'est pas migré (classe de test locale) : on
    # vérifie donc la LOGIQUE de save() sans toucher de vraie table. La
    # validation bout-en-bout du versioning (incrément réellement persisté,
    # conflit 409 STALE_RESOURCE) est faite au Sprint 2 sur `event`/`category`,
    # premières ressources réellement optimistes (Source A ADR-S-05) — Sprint 0
    # ne livre que le socle, pas un scénario métier complet (§80 master prompt).
    instance = _DummyVersionedModel(name="a")
    instance.pk = uuid.uuid4()  # simule une instance déjà persistée
    assert instance.version == 1
    # save() sur une instance avec PK doit transformer version en F("version")+1
    # avant l'appel réel à la base — on vérifie l'expression sans DB réelle.
    import unittest.mock as mock

    with (
        mock.patch("apps.core.models.models.Model.save"),
        mock.patch.object(_DummyVersionedModel, "refresh_from_db"),
    ):
        instance.save()
    assert hasattr(instance.version, "connector") or isinstance(
        instance.version, models.expressions.CombinedExpression
    )
