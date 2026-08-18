"""
Invariant de la sonde de disponibilité (P1-000).

`connect_timeout` de libpq est un ENTIER de secondes, de plancher 2, et la
valeur 0 y signifie « attendre indéfiniment ». Un délai applicatif fractionnaire
ou sous-seconde ne doit donc jamais l'atteindre tel quel : il produirait une
sonde sans délai de garde, en contradiction directe avec le §36.
"""

import pytest

from apps.core.views import libpq_connect_timeout


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        (2.0, 2),
        (2, 2),
        (5.0, 5),
        (4.6, 5),
        (4.4, 4),
        (0.5, 2),
        (0.0, 2),
        (1.0, 2),
        (-3.0, 2),
    ],
)
def test_timeout_is_always_an_integer_of_at_least_two_seconds(configured, expected):
    result = libpq_connect_timeout(configured)
    assert isinstance(result, int)
    assert result >= 2
    assert result == expected


def test_sub_second_timeout_never_degrades_to_infinite_wait():
    """0 signifie « aucune limite » pour libpq : jamais produit, quelle que soit l'entrée."""
    for configured in (0.0, 0.1, 0.49, 0.5, 0.9, 1.4):
        assert libpq_connect_timeout(configured) != 0
