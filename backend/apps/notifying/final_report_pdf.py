from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.access.models import EventFinalReport


def _money(cents: int) -> str:
    return f"{cents / 100:,.2f} €".replace(",", " ").replace(".", ",")


def build_final_report_pdf(*, report: EventFinalReport) -> bytes:
    """Construit le PDF du snapshot final, sans recalculer les données métier."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Rapport final — {report.event.name}",
        author="FANID",
    )
    styles = getSampleStyleSheet()
    title = styles["Title"]
    normal = styles["BodyText"]
    heading = styles["Heading2"]

    event = report.event
    story = [
        Paragraph("FANID — Rapport final d’événement", title),
        Spacer(1, 0.25 * cm),
        Paragraph(f"<b>Événement :</b> {event.name}", normal),
        Paragraph(
            f"<b>Terminé le :</b> {event.ends_at.astimezone().strftime('%d/%m/%Y à %H:%M')}",
            normal,
        ),
        Paragraph(
            f"<b>Rapport généré le :</b> {report.generated_at.astimezone().strftime('%d/%m/%Y à %H:%M')}",
            normal,
        ),
        Spacer(1, 0.45 * cm),
        Paragraph("Synthèse", heading),
    ]

    rows = [
        ["Indicateur", "Valeur"],
        ["Billets vendus", str(report.tickets_sold_count)],
        ["Billets utilisés", str(report.tickets_used_count)],
        ["Absents / no-show", str(report.tickets_absent_count)],
        ["Billets annulés", str(report.tickets_voided_count)],
        ["Chiffre d’affaires brut", _money(report.gross_revenue_cents)],
        ["Remboursements", _money(report.refunds_cents)],
        ["Chiffre d’affaires net", _money(report.net_revenue_cents)],
        ["Commission FANID", _money(report.commission_cents)],
        ["Net Organizer", _money(report.organizer_net_cents)],
    ]
    summary = Table(rows, colWidths=[10.8 * cm, 5.0 * cm])
    summary.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172554")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])
    )
    story.extend([summary, Spacer(1, 0.5 * cm), Paragraph("Scans par Scanner", heading)])

    scanner_rows = [["Scanner", "E-mail", "Scans", "Dernier scan"]]
    for scanner in report.scanner_stats:
        last_scan = scanner.get("last_scan_at") or "—"
        scanner_rows.append([
            str(scanner.get("name") or "—"),
            str(scanner.get("email") or "—"),
            str(scanner.get("scan_count") or 0),
            last_scan.replace("T", " ")[:16],
        ])

    if len(scanner_rows) == 1:
        scanner_rows.append(["Aucun scan enregistré", "—", "0", "—"])

    scanners = Table(scanner_rows, colWidths=[4.3 * cm, 5.8 * cm, 1.6 * cm, 4.1 * cm])
    scanners.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ])
    )
    story.extend([
        scanners,
        Spacer(1, 0.45 * cm),
        Paragraph(
            "Ce document est le snapshot final généré à la clôture de l’événement.",
            normal,
        ),
    ])

    document.build(story)
    return output.getvalue()
