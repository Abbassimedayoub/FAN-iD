"""
Ports (§19 master prompt / §2.3 Source B) — six frontières de test.

Chaque port est une classe abstraite (contrat), sans implémentation métier.
Les adaptateurs concrets vivent dans `apps.core.adapters` ; les sprints
suivants y ajoutent les implémentations réelles (Stripe, SES, S3, SSM) sans
jamais modifier ces contrats ni le code qui les consomme.
"""
from .device_lock import DeviceLockBackend
from .events import EventPublisher
from .notifications import NotificationSender
from .payments import PaymentGateway
from .secrets import SecretProvider
from .storage import ObjectStorage

__all__ = [
    "SecretProvider",
    "EventPublisher",
    "PaymentGateway",
    "NotificationSender",
    "ObjectStorage",
    "DeviceLockBackend",
]
