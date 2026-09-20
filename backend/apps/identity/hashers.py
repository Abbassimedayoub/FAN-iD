"""
Password hashing policy.

Django's `Argon2PasswordHasher` uses Argon2id, the variant recommended by
OWASP because it is resistant to both side-channel and time-memory tradeoff
attacks.

Parameters are pinned explicitly instead of relying on Django defaults that
may change across versions. Silent cost changes can unexpectedly alter login
latency just as silent weakening can reduce security.

The test settings replace this hasher with a fast one so the suite remains
practical. Development and production keep the hardened configuration.
"""

from django.contrib.auth.hashers import Argon2PasswordHasher


class FanIdArgon2PasswordHasher(Argon2PasswordHasher):
    """Argon2id with explicitly pinned parameters."""

    #: Number of iterations.
    time_cost = 3
    #: Memory in kibibytes; 65536 KiB = 64 MiB.
    memory_cost = 65536
    #: Number of parallel lanes.
    parallelism = 4
