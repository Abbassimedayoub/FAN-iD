"""
Tests du garde-fou du backend de notification.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.core.adapters.notifications import ConsoleSender, InMemorySender, build_notification_sender
from apps.core.checks import console_notifier_is_development_only


def test_the_console_backend_is_refused_outside_development(settings):
    settings.DEBUG = False
    settings.NOTIFICATION_BACKEND = "console"

    assert [e.id for e in console_notifier_is_development_only(None)] == ["core.E001"]


def test_the_console_backend_is_fine_in_development(settings):
    settings.DEBUG = True
    settings.NOTIFICATION_BACKEND = "console"

    assert console_notifier_is_development_only(None) == []


def test_a_real_backend_passes_the_check(settings):
    settings.DEBUG = False
    settings.NOTIFICATION_BACKEND = "memory"

    assert console_notifier_is_development_only(None) == []


def test_the_factory_honours_the_setting(settings):
    settings.NOTIFICATION_BACKEND = "memory"
    assert isinstance(build_notification_sender(), InMemorySender)

    settings.NOTIFICATION_BACKEND = "console"
    assert isinstance(build_notification_sender(), ConsoleSender)


def test_an_unknown_backend_refuses_to_start(settings):
    settings.NOTIFICATION_BACKEND = "pigeon-voyageur"

    with pytest.raises(ImproperlyConfigured):
        build_notification_sender()
