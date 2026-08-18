from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pytest
import yaml


class AlertLabels(TypedDict):
    severity: str


class AlertRule(TypedDict):
    alert: str
    expr: str
    for_: str
    labels: AlertLabels


ROOT = Path(__file__).resolve().parents[4]
ALERTS_FILE = ROOT / "infra" / "monitoring" / "alerts.yml"
PROMETHEUS_FILE = ROOT / "infra" / "monitoring" / "prometheus.yml"

if not ALERTS_FILE.exists() or not PROMETHEUS_FILE.exists():
    pytest.skip(
        "infra/monitoring n'est pas monte dans cet environnement",
        allow_module_level=True,
    )


def _rules() -> list[dict[str, object]]:
    data = yaml.safe_load(ALERTS_FILE.read_text(encoding="utf-8"))
    return data["groups"][0]["rules"]


def test_alerts_file_loads_and_contains_exactly_two_rules() -> None:
    data = yaml.safe_load(ALERTS_FILE.read_text(encoding="utf-8"))

    assert len(data["groups"]) == 1
    assert len(data["groups"][0]["rules"]) == 2

    names = {rule["alert"] for rule in data["groups"][0]["rules"]}
    assert names == {
        "FanidAuthTokenReuseDetected",
        "FanidAuthBadCredentialsSpike",
    }


def test_prometheus_references_the_alert_rules_file() -> None:
    data = yaml.safe_load(PROMETHEUS_FILE.read_text(encoding="utf-8"))

    assert data["rule_files"] == ["alerts.yml"]


def test_alert_severities_are_fixed() -> None:
    rules = {rule["alert"]: rule for rule in _rules()}

    reuse_labels = rules["FanidAuthTokenReuseDetected"]["labels"]
    bad_credentials_labels = rules["FanidAuthBadCredentialsSpike"]["labels"]

    assert isinstance(reuse_labels, dict)
    assert isinstance(bad_credentials_labels, dict)
    assert reuse_labels["severity"] == "critical"
    assert bad_credentials_labels["severity"] == "warning"


def test_critical_reuse_alert_contract() -> None:
    rules = {rule["alert"]: rule for rule in _rules()}
    rule = rules["FanidAuthTokenReuseDetected"]

    expr = rule["expr"]
    assert isinstance(expr, str)

    assert expr == "increase(fanid_auth_token_reuse_detected_total[5m]) > 0"
    assert "fanid_auth_token_reuse_detected_total > 0" not in expr
    assert rule["for"] == "0m"


def test_bad_credentials_alert_contract() -> None:
    rules = {rule["alert"]: rule for rule in _rules()}
    rule = rules["FanidAuthBadCredentialsSpike"]

    assert rule["expr"] == ('sum(rate(fanid_auth_login_total{result="bad_credentials"}[1m])) ' "* 60 > 50")
    assert rule["for"] == "2m"


def test_alert_expressions_reference_declared_business_metrics() -> None:
    metrics_source = (Path(__file__).resolve().parents[1] / "observability" / "metrics.py").read_text(
        encoding="utf-8"
    )

    expressions = " ".join(str(rule["expr"]) for rule in _rules())

    for metric_name in (
        "fanid_auth_token_reuse_detected_total",
        "fanid_auth_login_total",
    ):
        assert metric_name in expressions
        assert f'"{metric_name}"' in metrics_source
