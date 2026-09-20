"""
Readiness-probe timeout invariant.

libpq `connect_timeout` is an INTEGER number of seconds with a minimum effective
value of 2, while 0 means wait indefinitely. Fractional or sub-second
application timeouts must therefore never reach libpq unchanged.
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
    """libpq interprets 0 as no timeout, so this helper must never produce it."""
    for configured in (0.0, 0.1, 0.49, 0.5, 0.9, 1.4):
        assert libpq_connect_timeout(configured) != 0
