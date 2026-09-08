from __future__ import annotations

from celery import shared_task

from apps.access.models import EventFinalReport
from apps.core.adapters.notifications import build_notification_sender

from .final_report_pdf import build_final_report_pdf


@shared_task(name="notifying.organizer_final_report_email")
def send_organizer_final_report_email(*, event_id: str) -> dict:
    """Envoie à l’Organizer le PDF du snapshot final existant."""
    report = (
        EventFinalReport.objects.select_related("event", "event__organizer__user")
        .filter(event_id=event_id)
        .first()
    )
    if report is None:
        return {"sent": False, "reason": "report_missing"}

    organizer = report.event.organizer
    recipient = organizer.contact_email or organizer.user.email
    pdf = build_final_report_pdf(report=report)
    filename = f"fanid-rapport-final-{report.event_id}.pdf"

    build_notification_sender().send_email(
        to=recipient,
        subject=f"Rapport final — {report.event.name}",
        body=(
            f"Bonjour {organizer.user.first_name or ''},\n\n"
            f"Le rapport final de l’événement « {report.event.name} » "
            "est disponible en pièce jointe.\n\n"
            f"Net Organizer : {report.organizer_net_cents / 100:.2f} €.\n\n"
            "L’équipe FANID"
        ),
        attachments=[(filename, pdf, "application/pdf")],
    )
    return {"sent": True, "event_id": event_id, "filename": filename}
