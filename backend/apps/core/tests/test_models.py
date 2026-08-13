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


class _DummyUuidVersionedModel(UUIDModel, VersionedModel):
    """Combinaison REELLE du projet : PK UUID a defaut + compteur de version.

    identity.User, Organizer, Event et Category utilisent tous cette combinaison.
    Elle seule revele le defaut : default=uuid.uuid4 renseigne la cle primaire des
    la construction, donc le test if self.pk est vrai AVANT le premier INSERT.
    _DummyVersionedModel porte un AutoField implicite : sa PK reste None tant que
    la ligne est absente, ce qui masquait completement le probleme.
    """

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


def test_versioned_model_does_not_use_f_expression_on_insert():
    """
    Non-régression : une instance NEUVE ne doit jamais recevoir `F("version")+1`.

    Django refuse une expression `F()` sur un `INSERT` — elle référence une
    colonne de la ligne, qui n'existe pas encore. Le code d'origine testait
    `if self.pk`, or toutes les PK du projet ont `default=uuid.uuid4` : une
    instance neuve porte déjà une PK, donc TOUTE création partait sur le chemin
    « mise à jour » et échouait avec :

        ValueError: Failed to insert expression "Col(...) + Value(1)".
        F() expressions can only be used to update, not to insert.

    Le défaut est resté invisible tant qu'aucun modèle concret n'héritait de
    `VersionedModel`. `identity.User` est le premier — au Sprint 2 il aurait
    fait tomber le verrouillage optimiste de `event` et `category`.
    """
    import unittest.mock as mock

    instance = _DummyUuidVersionedModel(name="a")
    assert instance.pk is not None, "default=uuid.uuid4 renseigne la PK a la construction"
    assert instance._state.adding is True

    with (
        mock.patch("apps.core.models.models.Model.save"),
        mock.patch.object(_DummyUuidVersionedModel, "refresh_from_db"),
    ):
        instance.save()

    assert instance.version == 1
    assert not isinstance(instance.version, models.expressions.CombinedExpression)


def test_versioned_model_save_uses_f_expression_when_updating():
    # `_DummyVersionedModel` n'est pas migré (classe de test locale) : on
    # vérifie donc la LOGIQUE de save() sans toucher de vraie table. La
    # validation bout-en-bout du versioning (incrément réellement persisté,
    # conflit 409 STALE_RESOURCE) est faite au Sprint 2 sur `event`/`category`,
    # premières ressources réellement optimistes (Source A ADR-S-05) — Sprint 0
    # ne livre que le socle, pas un scénario métier complet (§80 master prompt).
    instance = _DummyVersionedModel(name="a")
    instance.pk = uuid.uuid4()
    # Une instance persistee se simule par _state.adding = False, PAS seulement
    # par une PK renseignee : toutes les PK du projet ont default=uuid.uuid4,
    # donc une instance NEUVE porte deja une PK. Ce test encodait la meme
    # hypothese fausse que le code — voila pourquoi il ne detectait rien.
    instance._state.adding = False
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
