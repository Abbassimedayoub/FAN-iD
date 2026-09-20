"""Unit tests for the shared base models."""

import uuid

from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel, VersionedModel


# Concrete test-only models used to exercise the abstract base classes.
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
    """Project-realistic combination: UUID primary key default plus version counter.

    This setup exposes insert/update detection bugs because `default=uuid.uuid4`
    populates the primary key before the first INSERT.
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
    Regression guard: a NEW instance must never receive `F("version") + 1`.

    Django rejects `F()` expressions on INSERT because they reference a row that
    does not yet exist. UUID defaults make `self.pk` truthy before insertion, so
    insert/update detection must rely on model state instead.
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
    # `_DummyVersionedModel` is not migrated, so this test verifies save() logic
    # without touching a real table.
    instance = _DummyVersionedModel(name="a")
    instance.pk = uuid.uuid4()
    # Simulate persistence with `_state.adding = False`, not merely by assigning a
    # primary key, because UUID defaults populate new instances immediately.
    instance._state.adding = False
    assert instance.version == 1
    # Updating a persisted instance must turn version into an F-expression before
    # the real database write; verify that expression without a real table.
    import unittest.mock as mock

    with (
        mock.patch("apps.core.models.models.Model.save"),
        mock.patch.object(_DummyVersionedModel, "refresh_from_db"),
    ):
        instance.save()
    assert hasattr(instance.version, "connector") or isinstance(
        instance.version, models.expressions.CombinedExpression
    )
