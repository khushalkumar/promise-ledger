from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#102A43")
TEAL = colors.HexColor("#0F766E")
INK = colors.HexColor("#243B53")
MUTED = colors.HexColor("#627D98")
PAPER = colors.HexColor("#F7FAFC")
LINE = colors.HexColor("#D9E2EC")


def _register_fonts() -> tuple[str, str]:
    regular = "/System/Library/Fonts/Supplemental/Arial.ttf"
    bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    if Path(regular).exists() and Path(bold).exists():
        pdfmetrics.registerFont(TTFont("ContractSans", regular))
        pdfmetrics.registerFont(TTFont("ContractSans-Bold", bold))
        return "ContractSans", "ContractSans-Bold"
    return "Helvetica", "Helvetica-Bold"


REGULAR_FONT, BOLD_FONT = _register_fonts()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "Eyebrow",
            parent=base["Normal"],
            fontName=BOLD_FONT,
            fontSize=8,
            leading=10,
            textColor=TEAL,
            uppercase=True,
            spaceAfter=6,
        ),
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName=BOLD_FONT,
            fontSize=24,
            leading=29,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName=REGULAR_FONT,
            fontSize=10,
            leading=14,
            textColor=MUTED,
            spaceAfter=14,
        ),
        "heading": ParagraphStyle(
            "Heading",
            parent=base["Heading2"],
            fontName=BOLD_FONT,
            fontSize=12,
            leading=15,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=9.5,
            leading=14,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontName=REGULAR_FONT,
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
        ),
        "signature": ParagraphStyle(
            "Signature",
            parent=base["Normal"],
            fontName=REGULAR_FONT,
            fontSize=8,
            leading=11,
            textColor=INK,
        ),
        "notice": ParagraphStyle(
            "Notice",
            parent=base["Normal"],
            fontName=BOLD_FONT,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#7C2D12"),
            alignment=TA_CENTER,
        ),
    }


STYLES = _styles()


def _page(canvas, document) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 9 * mm, width, 9 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont(BOLD_FONT, 7.5)
    canvas.drawString(20 * mm, height - 5.8 * mm, "TASKLANE  /  AGREEMENT")
    canvas.setFillColor(MUTED)
    canvas.setFont(REGULAR_FONT, 7)
    canvas.drawRightString(width - 20 * mm, 10 * mm, f"Page {document.page}")
    canvas.setStrokeColor(LINE)
    canvas.line(20 * mm, 14 * mm, width - 20 * mm, 14 * mm)
    canvas.restoreState()


def _metadata_table(rows: Sequence[tuple[str, str]]) -> Table:
    data = [
        [Paragraph(label, STYLES["small"]), Paragraph(value, STYLES["body"])]
        for label, value in rows
    ]
    table = Table(data, colWidths=[36 * mm, 124 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PAPER),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _signature_block(left_party: str, right_party: str) -> Table:
    cells = []
    for party in (left_party, right_party):
        cells.append(
            [
                Paragraph(f"<b>{party}</b>", STYLES["signature"]),
                Spacer(1, 12 * mm),
                HRFlowable(width="100%", thickness=0.5, color=MUTED),
                Paragraph("Authorized signatory", STYLES["small"]),
                Spacer(1, 5 * mm),
                HRFlowable(width="100%", thickness=0.5, color=MUTED),
                Paragraph("Name and date", STYLES["small"]),
            ]
        )
    table = Table([cells], colWidths=[78 * mm, 78 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _build_contract(
    output: Path,
    *,
    title: str,
    version: str,
    effective_date: str,
    parties: tuple[str, str],
    introduction: str,
    sections: Sequence[tuple[str, Sequence[str]]],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=title,
        author="Tasklane Demo",
        subject="Fictional Promise Ledger demonstration contract",
    )
    story = [
        Spacer(1, 3 * mm),
        Paragraph("PROMISE LEDGER DEMO CONTRACT", STYLES["eyebrow"]),
        Paragraph(title, STYLES["title"]),
        Paragraph(
            "Fictional agreement prepared for the neatHack 2026 Promise Ledger demonstration.",
            STYLES["subtitle"],
        ),
        _metadata_table(
            [
                ("Document", version),
                ("Effective date", effective_date),
                ("Parties", f"{parties[0]} and {parties[1]}"),
                ("Classification", "Synthetic demonstration data - not legally binding"),
            ]
        ),
        Spacer(1, 6 * mm),
        Paragraph(introduction, STYLES["body"]),
    ]
    for heading, paragraphs in sections:
        story.append(Paragraph(heading, STYLES["heading"]))
        story.extend(Paragraph(text, STYLES["body"]) for text in paragraphs)
    story.extend(
        [
            Spacer(1, 8 * mm),
            Paragraph("Acknowledged for demonstration purposes", STYLES["heading"]),
            _signature_block(*parties),
            Spacer(1, 8 * mm),
            Paragraph(
                "NOT A REAL CONTRACT - ALL NAMES, TERMS, AND SIGNATURE LINES ARE FICTIONAL",
                STYLES["notice"],
            ),
        ]
    )
    document.build(story, onFirstPage=_page, onLaterPages=_page)


def render_contracts(output_directory: Path) -> list[Path]:
    northwind = output_directory / "Northwind_DPA_v3.pdf"
    acme = output_directory / "Acme_MSA_2026.pdf"
    _build_contract(
        northwind,
        title="Northwind Data Processing Addendum",
        version="Version 3",
        effective_date="1 October 2026",
        parties=("Northwind Analytics Ltd.", "Tasklane Software Inc."),
        introduction=(
            "This Data Processing Addendum forms part of the fictional services agreement "
            "between the parties and defines measurable obligations for customer personal data."
        ),
        sections=[
            (
                "7.2  Deletion and backup retention",
                [
                    "Following termination of the Services, Tasklane will delete Northwind's "
                    "customer personal data within 30 days. Deletion includes application "
                    "records, audit events, exports, attachments, and backups controlled by "
                    "Tasklane.",
                    "Database snapshots and other retained backups must not remain available "
                    "beyond the same 30-day period.",
                ],
            ),
            (
                "9.1  Data residency",
                [
                    "Customer personal data belonging to Northwind's European users will be "
                    "stored and processed only in eu-west-1."
                ],
            ),
            (
                "11.3  Subprocessor notice",
                [
                    "Tasklane will notify Northwind at least 30 days before adding a new "
                    "subprocessor and will maintain a current subprocessor list available to "
                    "Northwind."
                ],
            ),
        ],
    )
    _build_contract(
        acme,
        title="Acme Master Services Agreement",
        version="2026 Edition",
        effective_date="1 October 2026",
        parties=("Acme Operations GmbH", "Tasklane Software Inc."),
        introduction=(
            "This fictional Master Services Agreement defines the product, availability, and "
            "security commitments used in the Promise Ledger benchmark."
        ),
        sections=[
            (
                "4.1  Business plan features",
                [
                    "Tasklane will make SSO configuration available to administrators of every "
                    "Business plan workspace."
                ],
            ),
            (
                "6.2  Availability",
                [
                    "Tasklane will maintain 99.9% monthly service availability. If availability "
                    "falls below 99.9%, eligible customers may request service credits under the "
                    "published service-level schedule."
                ],
            ),
            (
                "8.1  Security controls",
                [
                    "Tasklane will encrypt customer data at rest and require multi-factor "
                    "authentication for administrative accounts."
                ],
            ),
            (
                "10.4  Termination",
                [
                    "On termination, Tasklane will return or delete customer content as required "
                    "by the applicable data processing addendum."
                ],
            ),
        ],
    )
    return [northwind, acme]


def main() -> None:
    parser = argparse.ArgumentParser(description="Render fictional Promise Ledger contracts")
    parser.add_argument("--output", type=Path, default=Path("contracts"))
    args = parser.parse_args()
    for path in render_contracts(args.output):
        print(path)


if __name__ == "__main__":
    main()
