"""
Case-insensitive email field backed by PostgreSQL `citext`.

Django used to provide `CIEmailField` in `django.contrib.postgres.fields`,
but it was deprecated in 4.2 and removed in 5.1. This project runs on Django
5.2, so a small custom field is required.

`citext` is preferred over a functional
`UniqueConstraint(Lower("email"))` because comparisons become
case-insensitive everywhere: equality filters, joins, and `get()`. Callers do
not need to remember to apply `LOWER()`.

On PostgreSQL, inserting `Fan@Example.TEST` and then
`fan@example.test` violates the unique index, and querying with another case
variant finds the same row.
"""

from django.db import models


class CITextEmailField(models.EmailField):
    """
    `EmailField` stored as `citext` on PostgreSQL.

    On another backend, fall back to the parent field type. Django-level email
    validation remains the same; only database-level case-insensitive behavior
    is lost. The fallback keeps model inspection usable outside PostgreSQL.
    """

    def db_type(self, connection) -> str | None:
        if connection.vendor == "postgresql":
            return "citext"
        return super().db_type(connection)
