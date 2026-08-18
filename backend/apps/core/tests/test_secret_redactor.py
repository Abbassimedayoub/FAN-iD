"""SecretRedactor : masque tous les motifs, y compris imbriqués (§55 master prompt)."""

import json
import logging

from apps.core.observability.logging import JsonFormatter, SecretRedactor

_REDACTED = "***REDACTED***"


def test_redacts_top_level_sensitive_keys():
    result = SecretRedactor.redact({"password": "hunter2", "username": "bob"})
    assert result["password"] == _REDACTED
    assert result["username"] == "bob"


def test_redacts_case_insensitively_and_partial_match():
    result = SecretRedactor.redact({"Authorization": "Bearer xyz", "API_KEY": "abc", "seed_value": "s3cr3t"})
    assert result["Authorization"] == _REDACTED
    assert result["API_KEY"] == _REDACTED
    assert result["seed_value"] == _REDACTED


def test_redacts_nested_dict():
    result = SecretRedactor.redact({"user": {"token": "abc123", "name": "bob"}})
    assert result["user"]["token"] == _REDACTED
    assert result["user"]["name"] == "bob"


def test_redacts_dict_inside_list():
    result = SecretRedactor.redact({"items": [{"card": "4242 4242"}, {"safe": "value"}]})
    assert result["items"][0]["card"] == _REDACTED
    assert result["items"][1]["safe"] == "value"


def test_non_sensitive_payload_is_unchanged():
    payload = {"event_id": "abc", "count": 3}
    assert SecretRedactor.redact(payload) == payload


def test_json_formatter_never_emits_raw_secret_in_log_line():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="fanid.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="stripe_call",
        args=(),
        exc_info=None,
    )
    record.stripe_secret_key = "sk_live_should_never_appear"
    line = formatter.format(record)
    payload = json.loads(line)

    assert "sk_live_should_never_appear" not in line
    assert payload["stripe_secret_key"] == _REDACTED
