import uuid

from apps.identity.services.scanner_accounts import derive_scanner_temporary_password


def test_scanner_temporary_password_has_no_fixed_fanid_pattern():
    first = derive_scanner_temporary_password(
        invitation_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        generation=1,
    )
    second = derive_scanner_temporary_password(
        invitation_id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
        generation=1,
    )

    assert len(first) == 24
    assert len(second) == 24
    assert first != second

    assert not first.startswith("FiD!")
    assert not second.startswith("FiD!")
    assert not first.endswith("a9Z!")
    assert not second.endswith("a9Z!")

    for password in (first, second):
        assert any(character.islower() for character in password)
        assert any(character.isupper() for character in password)
        assert any(character.isdigit() for character in password)
        assert any(character in "!@#$%_-" for character in password)


def test_scanner_temporary_password_changes_with_generation():
    invitation_id = uuid.UUID("33333333-3333-4333-8333-333333333333")

    first = derive_scanner_temporary_password(
        invitation_id=invitation_id,
        generation=1,
    )
    second = derive_scanner_temporary_password(
        invitation_id=invitation_id,
        generation=2,
    )

    assert first != second
