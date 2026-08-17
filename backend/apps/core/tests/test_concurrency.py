import pytest

from apps.core.concurrency import format_etag, parse_if_match, versioned_update
from apps.core.exceptions import PreconditionFailed, StaleResourceError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", 1),
        ("42", 42),
        ('"1"', 1),
        ('"42"', 42),
        (" 7 ", 7),
    ],
)
def test_parse_if_match_accepts_version(raw, expected):
    assert parse_if_match(raw) == expected


@pytest.mark.parametrize("raw", [None, "", " ", "abc", "0", "-1", 'W/"3"'])
def test_parse_if_match_rejects_missing_or_invalid_version(raw):
    with pytest.raises(PreconditionFailed):
        parse_if_match(raw)


def test_format_etag():
    assert format_etag(3) == '"3"'


@pytest.mark.django_db
def test_versioned_update_updates_only_expected_version(user):
    original_version = user.version

    new_version = versioned_update(
        model=type(user),
        pk=user.pk,
        expected_version=original_version,
        updates={"first_name": "Versioned"},
    )

    user.refresh_from_db()

    assert new_version == original_version + 1
    assert user.version == original_version + 1
    assert user.first_name == "Versioned"


@pytest.mark.django_db
def test_versioned_update_rejects_stale_version_with_current_version(user):
    original_version = user.version

    versioned_update(
        model=type(user),
        pk=user.pk,
        expected_version=original_version,
        updates={"first_name": "Winner"},
    )

    with pytest.raises(StaleResourceError) as exc_info:
        versioned_update(
            model=type(user),
            pk=user.pk,
            expected_version=original_version,
            updates={"first_name": "Loser"},
        )

    assert exc_info.value.details == {"current_version": original_version + 1}

    user.refresh_from_db()
    assert user.first_name == "Winner"
    assert user.version == original_version + 1


@pytest.mark.django_db
def test_versioned_update_does_not_allow_caller_to_set_version(user):
    with pytest.raises(ValueError, match="version"):
        versioned_update(
            model=type(user),
            pk=user.pk,
            expected_version=user.version,
            updates={"version": 999},
        )
