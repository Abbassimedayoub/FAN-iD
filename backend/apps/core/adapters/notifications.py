from apps.core.interfaces import NotificationSender


class InMemorySender(NotificationSender):
    """Tests / dev sans SMTP réel — capture les envois pour assertion."""

    def __init__(self):
        self.emails_sent: list[dict] = []
        self.pushes_sent: list[dict] = []

    def send_email(self, to: str, subject: str, body: str, **kwargs) -> None:
        self.emails_sent.append({"to": to, "subject": subject, "body": body, **kwargs})

    def send_push(self, device_token: str, title: str, body: str, **kwargs) -> None:
        self.pushes_sent.append({"device_token": device_token, "title": title, "body": body, **kwargs})
