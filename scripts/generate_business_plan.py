# ruff: noqa: E501 - long report copy and table style declarations stay readable inline.
from __future__ import annotations

import csv
from pathlib import Path

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).parents[1]
INPUT = ROOT / "evidence" / "cfo_inputs.csv"
OUTPUT = ROOT / "docs" / "business_plan.pdf"

INK = colors.HexColor("#17233D")
MUTED = colors.HexColor("#65728A")
TEAL = colors.HexColor("#0E8A83")
MINT = colors.HexColor("#DFF4EF")
CREAM = colors.HexColor("#F7F5EF")
CORAL = colors.HexColor("#E86A55")
WHITE = colors.white


class Pill(Flowable):
    def __init__(self, label: str, value: str, width: float = 53 * mm):
        super().__init__()
        self.label = label
        self.value = value
        self.width = width
        self.height = 23 * mm

    def draw(self) -> None:
        canvas = self.canv
        canvas.setFillColor(CREAM)
        canvas.roundRect(0, 0, self.width, self.height, 4 * mm, fill=1, stroke=0)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.drawString(5 * mm, 15.5 * mm, self.label.upper())
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(5 * mm, 6 * mm, self.value)


def _money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def _rows() -> list[dict[str, str]]:
    with INPUT.open(newline="") as stream:
        return list(csv.DictReader(stream))


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=29,
            leading=32,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=8 * mm,
        ),
        "kicker": ParagraphStyle(
            "Kicker",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=TEAL,
            tracking=1.2,
            spaceAfter=3 * mm,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=INK,
            spaceBefore=3 * mm,
            spaceAfter=5 * mm,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=INK,
            spaceBefore=5 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=14,
            textColor=INK,
            spaceAfter=3 * mm,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
        ),
        "table": ParagraphStyle(
            "Table",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.5,
            textColor=INK,
        ),
        "table_bold": ParagraphStyle(
            "TableBold",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9.5,
            textColor=INK,
        ),
        "callout": ParagraphStyle(
            "Callout",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=18,
            textColor=INK,
            alignment=TA_CENTER,
        ),
    }


def _header_footer(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#D9DEE8"))
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawString(18 * mm, height - 10 * mm, "PROMISE LEDGER  /  BUSINESS MODEL")
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"EL EL EMS  /  {doc.page}")
    canvas.restoreState()


def _scenario_chart(rows: list[dict[str, str]]) -> Drawing:
    drawing = Drawing(165 * mm, 72 * mm)
    chart = VerticalBarChart()
    chart.x = 18 * mm
    chart.y = 10 * mm
    chart.height = 48 * mm
    chart.width = 135 * mm
    chart.data = [
        tuple(float(row["monthly_revenue_usd"]) / 1000 for row in rows),
        tuple(float(row["total_cogs_usd"]) / 1000 for row in rows),
    ]
    chart.categoryAxis.categoryNames = [row["scenario"].title() for row in rows]
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 30
    chart.valueAxis.valueStep = 5
    chart.valueAxis.labelTextFormat = "$%dK"
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.strokeColor = colors.HexColor("#D9DEE8")
    chart.bars[0].fillColor = TEAL
    chart.bars[1].fillColor = colors.HexColor("#AEB8CA")
    chart.bars.strokeColor = None
    chart.groupSpacing = 9
    chart.barSpacing = 1
    drawing.add(chart)
    drawing.add(String(60 * mm, 68 * mm, "Revenue", fontName="Helvetica-Bold", fontSize=7, fillColor=TEAL))
    drawing.add(String(93 * mm, 68 * mm, "COGS", fontName="Helvetica-Bold", fontSize=7, fillColor=colors.HexColor("#7D899C")))
    return drawing


def build() -> None:
    rows = _rows()
    base = rows[1]
    styles = _styles()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title="Promise Ledger - Business Plan",
        author="el el ems",
        subject="Measured unit economics and scenario plan",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_header_footer)])

    story = [
        Spacer(1, 18 * mm),
        Paragraph("MEASURED UNIT ECONOMICS", styles["kicker"]),
        Paragraph("Promise Ledger", styles["title"]),
        Paragraph(
            "Contract verification that turns signed clauses into repeatable system checks, traceable evidence, and reviewable remediation.",
            ParagraphStyle("Deck", parent=styles["body"], fontSize=14, leading=20, textColor=MUTED, spaceAfter=12 * mm),
        ),
        Table(
            [[Pill("Measured audit cost", "$0.016505"), Pill("Base gross margin", "75.84%"), Pill("Break-even", "~386 contracts")]],
            colWidths=[56 * mm] * 3,
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm)]),
        ),
        Spacer(1, 15 * mm),
        Table(
            [[Paragraph("The wedge", styles["h2"]), Paragraph("The business", styles["h2"])],
             [Paragraph("Existing contract tools extract obligations. Promise Ledger goes further: it tests each signed promise against code, data, and infrastructure, and preserves the evidence behind every verdict.", styles["body"]),
              Paragraph("Start with security and legal teams managing high-value B2B contracts. Sell monitoring as a platform subscription, with contract count as the expansion metric.", styles["body"])]],
            colWidths=[82 * mm, 82 * mm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, -1), MINT), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B9DDD5")), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B9DDD5")), ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm), ("TOPPADDING", (0, 0), (-1, -1), 3 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm)]),
        ),
        Spacer(1, 14 * mm),
        Paragraph("Prepared for neatHack 2026 by team el el ems", styles["small"]),
        PageBreak(),
        Paragraph("EVIDENCE BEFORE ASSUMPTIONS", styles["kicker"]),
        Paragraph("One audit, measured", styles["h1"]),
        Paragraph(
            "The baseline is a saved live run over three documents and nine canonical promises. Provider usage was captured with the audit result, so token volume is measured rather than estimated.",
            styles["body"],
        ),
        Table(
            [
                ["Documents", "Promises", "Model calls", "Prompt tokens", "Completion tokens"],
                ["3", "9", "3", "2,886", "929"],
            ],
            colWidths=[32 * mm, 32 * mm, 32 * mm, 34 * mm, 34 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 1), (-1, 1), CREAM),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9DEE8")),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]),
        ),
        Paragraph("Cost equation", styles["h2"]),
        Table(
            [[Paragraph("(2,886 / 1M x $2.50) + (929 / 1M x $10.00) = <b>$0.016505 per audit</b>", styles["callout"]) ]],
            colWidths=[164 * mm],
            style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), MINT), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B9DDD5")), ("TOPPADDING", (0, 0), (-1, -1), 8 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 8 * mm)]),
        ),
        Paragraph("What actually drives margin", styles["h2"]),
        Paragraph(
            "Model tokens are not the constraint. At the base volume, model API expense is only $26.41 per month. Infrastructure, review support, security work, and customer operations dominate COGS. The pricing experiment should therefore validate willingness to pay and support intensity, not optimize pennies of inference first.",
            styles["body"],
        ),
        Paragraph("Pricing hypothesis", styles["h2"]),
        Table(
            [
                [Paragraph("PER CONTRACT", styles["kicker"]), Paragraph("PLATFORM - RECOMMENDED", styles["kicker"])],
                [Paragraph("$49 per monitored contract per month, including six scheduled or change-triggered audits.", styles["body"]), Paragraph("$499 per month including 20 contracts, then $19 for each additional contract.", styles["body"])],
            ],
            colWidths=[82 * mm, 82 * mm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (0, -1), CREAM), ("BACKGROUND", (1, 0), (1, -1), MINT), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9DEE8")), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9DEE8")), ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm), ("TOPPADDING", (0, 0), (-1, -1), 4 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm)]),
        ),
        PageBreak(),
        Paragraph("THREE OPERATING CASES", styles["kicker"]),
        Paragraph("Scale changes the economics", styles["h1"]),
        _scenario_chart(rows),
        Table(
            [["Scenario", "Contracts", "Revenue", "COGS", "Gross margin", "Net cash flow", "Runway"]]
            + [
                [
                    row["scenario"].title(),
                    f"{int(row['monitored_contracts']):,}",
                    _money(float(row["monthly_revenue_usd"])),
                    _money(float(row["total_cogs_usd"])),
                    f"{float(row['gross_margin_percent']):.2f}%",
                    _money(float(row["monthly_net_cash_flow_usd"])),
                    "Positive" if row["runway_months"] == "not_applicable" else f"{float(row['runway_months']):.2f} mo",
                ]
                for row in rows
            ],
            colWidths=[25 * mm, 21 * mm, 25 * mm, 24 * mm, 27 * mm, 28 * mm, 25 * mm],
            repeatRows=1,
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.2),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, CREAM]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9DEE8")),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5 * mm),
            ]),
        ),
        Paragraph("Base case", styles["h2"]),
        Paragraph(
            f"At {int(base['monitored_contracts']):,} contracts, monthly revenue reaches {_money(float(base['monthly_revenue_usd']))} at a {float(base['gross_margin_percent']):.2f}% gross margin. The company deliberately remains in investment mode with {_money(float(base['monthly_net_cash_flow_usd']))} monthly net cash flow and 8.22 months of runway on $50,000 opening cash.",
            styles["body"],
        ),
        Paragraph("Break-even", styles["h2"]),
        Paragraph(
            "Base-case contribution is approximately $32.83 per monitored contract per month after variable model, observability, and per-contract support. With about $12,650 of fixed monthly infrastructure and operating expense, break-even is approximately 386 monitored contracts.",
            styles["body"],
        ),
        PageBreak(),
        Paragraph("WHAT TO LEARN NEXT", styles["kicker"]),
        Paragraph("A finance plan for discovery", styles["h1"]),
        Paragraph("The model is a decision tool, not a forecast promise. Each assumption has a corresponding customer or operational experiment.", styles["body"]),
        KeepTogether([
            Table(
                [
                    ["Assumption", "Experiment", "Decision signal"],
                    [Paragraph("Legal and security teams will pay for continuous clause verification.", styles["table_bold"]), Paragraph("Run 10 design-partner demos using one signed DPA and one live codebase.", styles["table"]), Paragraph("At least 3 teams agree to a paid pilot at $499/month.", styles["table"])],
                    [Paragraph("Support load stays below $6 per contract per month at scale.", styles["table_bold"]), Paragraph("Track reviewer minutes, escalations, and unverifiable promises for every pilot.", styles["table"]), Paragraph("Median human review remains under 10 minutes per changed contract.", styles["table"])],
                    [Paragraph("A platform plan sells better than per-contract pricing.", styles["table_bold"]), Paragraph("Quote both packages in alternating discovery calls.", styles["table"]), Paragraph("Platform offer wins without materially lowering annual contract value.", styles["table"])],
                    [Paragraph("Audit quality holds as contract volume grows.", styles["table_bold"]), Paragraph("Expand the seeded benchmark and review every false hold.", styles["table"]), Paragraph("No false holds in the release gate; unverifiable stays explicit.", styles["table"])],
                ],
                colWidths=[50 * mm, 66 * mm, 48 * mm],
                repeatRows=1,
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), INK),
                    ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.4),
                    ("LEADING", (0, 0), (-1, -1), 10),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, CREAM]),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9DEE8")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 3.2 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2 * mm),
                ]),
            ),
        ]),
        Paragraph("Accounting boundary", styles["h2"]),
        Paragraph(
            "Measured inputs: token usage, documents, promises, and model calls from the saved live audit. Assumed inputs: provider prices, infrastructure, support, payroll, and sales pace. Replace assumed values with cfo.ai actuals and invoices before fundraising, hiring, or pricing decisions.",
            styles["body"],
        ),
        Spacer(1, 8 * mm),
        Table(
            [[Paragraph("Recommended next move: recruit three paid design partners before optimizing inference cost.", styles["callout"]) ]],
            colWidths=[164 * mm],
            style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), MINT), ("BOX", (0, 0), (-1, -1), 0.7, TEAL), ("TOPPADDING", (0, 0), (-1, -1), 8 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 8 * mm), ("LEFTPADDING", (0, 0), (-1, -1), 8 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 8 * mm)]),
        ),
        Spacer(1, 10 * mm),
        Paragraph("Source: evidence/cfo_inputs.csv and evidence/run_live_audit.json. Prepared October 11, 2026.", styles["small"]),
    ]

    doc.build(story)


if __name__ == "__main__":
    build()
