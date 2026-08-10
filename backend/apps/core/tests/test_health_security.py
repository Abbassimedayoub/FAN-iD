"""
P1.B — timeout DB réellement appliqué + masquage des détails d'infrastructure
dans /health/ready (aucun test ici ne nécessite une vraie base : psycopg est
mocké pour observer précisément les paramètres passés et le comportement en
cas d'échec).
"""
from unittest import mock

from apps.core.views import ReadinessView


def test_check_database_applies_real_connect_and_statement_timeout():
    fake_connection = mock.MagicMock()
    fake_connection.__enter__.return_value = fake_connection
    fake_cursor = mock.MagicMock()
    fake_cursor.__enter__.return_value = fake_cursor
    fake_connection.cursor.return_value = fake_cursor

    with mock.patch("apps.core.views.connections") as mocked_connections, mock.patch(
        "psycopg.connect", return_value=fake_connection
    ) as mocked_connect:
        mocked_connections.__getitem__.return_value.get_connection_params.return_value = {
            "host": "postgres",
            "dbname": "fanid",
        }

        result = ReadinessView._check_database(timeout=2.0)

    assert result["status"] == "ok"
    _, kwargs = mocked_connect.call_args
    assert kwargs["connect_timeout"] == 2.0
    assert "statement_timeout=2000" in kwargs["options"]


def test_check_database_never_leaks_exception_text_to_response():
    sensitive_message = "connection to server at postgres-internal-host.vpc failed: password authentication failed for user fanid_prod"

    with mock.patch("apps.core.views.connections") as mocked_connections, mock.patch(
        "psycopg.connect", side_effect=RuntimeError(sensitive_message)
    ):
        mocked_connections.__getitem__.return_value.get_connection_params.return_value = {}

        result = ReadinessView._check_database(timeout=2.0)

    assert result["status"] == "down"
    assert sensitive_message not in str(result)
    assert "fanid_prod" not in str(result)
    assert "password" not in str(result).lower()


def test_check_redis_never_leaks_exception_text_to_response():
    sensitive_message = "Error connecting to redis-internal.vpc:6379 with password 'sup3rs3cr3t'"

    with mock.patch("redis.from_url", side_effect=RuntimeError(sensitive_message)):
        result = ReadinessView._check_redis(timeout=2.0)

    assert result["status"] == "degraded"
    assert sensitive_message not in str(result)
    assert "sup3rs3cr3t" not in str(result)


def test_check_celery_never_leaks_exception_text_to_response():
    sensitive_message = "AMQP broker error: amqp://user:pass@broker-internal:5672"

    with mock.patch("config.celery.app") as mocked_app:
        mocked_app.control.ping.side_effect = RuntimeError(sensitive_message)
        result = ReadinessView._check_celery(timeout=2.0)

    assert result["status"] == "degraded"
    assert sensitive_message not in str(result)


def test_check_celery_no_heartbeat_is_a_safe_fixed_string_not_removed():
    """Le message fixe 'no heartbeat' n'est pas dérivé d'une exception — il reste (§P1.B.2, pas une sur-correction)."""
    with mock.patch("config.celery.app") as mocked_app:
        mocked_app.control.ping.return_value = []
        result = ReadinessView._check_celery(timeout=2.0)

    assert result == {"status": "degraded", "detail": "no heartbeat"}
