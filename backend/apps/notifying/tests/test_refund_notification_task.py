from __future__ import annotations

import uuid
from types import SimpleNamespace

from apps.notifying.refund_notification_tasks import send_refund_succeeded_email


def test_refund_notification_task_uses_public_payments_api(
    monkeypatch,
):
    refund_id = uuid.uuid4()
    lookups = []

    summary = SimpleNamespace(
        id=refund_id,
        buyer_email="refund-buyer@example.test",
        buyer_first_name="Amina",
        event_name="Refund event",
        amount_cents=1234,
    )

    def fake_lookup(*, refund_id):
        lookups.append(refund_id)
        return summary

    class FakeSender:
        def __init__(self):
            self.emails_sent = []

        def send_email(self, **kwargs):
            self.emails_sent.append(kwargs)

    sender = FakeSender()

    monkeypatch.setattr(
        "apps.notifying.refund_notification_tasks." "get_payment_refund_notification_summary",
        fake_lookup,
    )
    monkeypatch.setattr(
        "apps.notifying.refund_notification_tasks." "build_notification_sender",
        lambda: sender,
    )

    result = send_refund_succeeded_email.run(
        refund_id=str(refund_id),
    )

    assert lookups == [refund_id]
    assert result == {
        "sent": True,
        "refund_id": str(refund_id),
    }
    assert len(sender.emails_sent) == 1
    assert sender.emails_sent[0]["to"] == summary.buyer_email
    assert "Refund event" in sender.emails_sent[0]["subject"]
    assert "12,34 €" in sender.emails_sent[0]["body"]
