"""
Ports — six testable boundaries.

Each port is an abstract contract with no business implementation. Concrete
adapters live in `apps.core.adapters`; real integrations can be added there
without changing these contracts or the code that consumes them.
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
