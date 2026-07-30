from __future__ import annotations

import textwrap
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "manuale-utente.md"
OUTPUT_DIR = ROOT / "output" / "pdf"
TMP_DIR = ROOT / "tmp" / "pdfs"
OUTPUT_PDF = OUTPUT_DIR / "manuale-utente-raspberry-wifi-portal.pdf"
DOCS_PDF = ROOT / "docs" / "manuale-utente-raspberry-wifi-portal.pdf"
CODE_WRAP_WIDTH = 88
DOCUMENT_VERSION = "1.17.0"
DOCUMENT_DATE = "30 luglio 2026"


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitlePage",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#143b67"),
            alignment=TA_CENTER,
            spaceAfter=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#14532d"),
            spaceBefore=12,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1f2937"),
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyTextCustom",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#111827"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletCustom",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            leftIndent=14,
            firstLineIndent=-8,
            bulletIndent=0,
            textColor=colors.HexColor("#111827"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeBlock",
            fontName="Courier",
            fontSize=8.7,
            leading=11.5,
            textColor=colors.HexColor("#0f172a"),
            backColor=colors.HexColor("#eef4fb"),
            borderColor=colors.HexColor("#c8d7ea"),
            borderWidth=0.6,
            borderPadding=7,
            borderRadius=4,
            spaceBefore=4,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallMuted",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#4b5563"),
            alignment=TA_CENTER,
        )
    )
    return styles


def escape_text(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def apply_inline_markup(text: str) -> str:
    escaped = escape_text(text)
    parts = escaped.split("`")
    if len(parts) == 1:
        return escaped
    rebuilt: list[str] = []
    for index, part in enumerate(parts):
        if index % 2 == 1:
            rebuilt.append(f"<font name='Courier'>{part}</font>")
        else:
            rebuilt.append(part)
    return "".join(rebuilt)


def wrap_code_block(lines: list[str]) -> str:
    wrapped_lines: list[str] = []
    for line in lines:
        if not line.strip():
            wrapped_lines.append(" ")
            continue

        wrapped = textwrap.wrap(
            line,
            width=CODE_WRAP_WIDTH,
            break_long_words=True,
            break_on_hyphens=False,
            subsequent_indent="  ",
        )
        wrapped_lines.extend(wrapped or [" "])

    return "\n".join(wrapped_lines)


def add_box(drawing: Drawing, x: float, y: float, width: float, height: float, title: str, subtitle: str, fill: str) -> None:
    drawing.add(Rect(x, y, width, height, rx=8, ry=8, fillColor=colors.HexColor(fill), strokeColor=colors.HexColor("#9eb6d8"), strokeWidth=1))
    drawing.add(String(x + 10, y + height - 18, title, fontName="Helvetica-Bold", fontSize=9.5, fillColor=colors.HexColor("#10243d")))
    drawing.add(String(x + 10, y + height - 34, subtitle, fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#334155")))


def add_arrow(drawing: Drawing, x1: float, y1: float, x2: float, y2: float, label: str) -> None:
    drawing.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#2563eb"), strokeWidth=1.4))
    drawing.add(
        Polygon(
            [x2, y2, x2 - 7, y2 + 4, x2 - 7, y2 - 4],
            fillColor=colors.HexColor("#2563eb"),
            strokeColor=colors.HexColor("#2563eb"),
        )
    )
    if label:
        drawing.add(String((x1 + x2) / 2 - 34, y1 + 8, label, fontName="Helvetica", fontSize=7.5, fillColor=colors.HexColor("#1e40af")))


def workflow_diagram(title: str, steps: list[tuple[str, str, str]], note: str = "") -> Drawing:
    width = 16.0 * cm
    height = 4.2 * cm
    drawing = Drawing(width, height)

    drawing.add(Rect(0, 0, width, height, rx=10, ry=10, fillColor=colors.HexColor("#f8fbff"), strokeColor=colors.HexColor("#c8d7ea"), strokeWidth=0.8))
    drawing.add(String(12, height - 22, title, fontName="Helvetica-Bold", fontSize=10, fillColor=colors.HexColor("#14532d")))

    box_count = len(steps)
    box_width = 84
    gap = (width - 24 - (box_width * box_count)) / max(box_count - 1, 1)
    box_y = 42
    box_height = 44

    for index, (step_title, subtitle, fill) in enumerate(steps):
        x = 12 + index * (box_width + gap)
        add_box(drawing, x, box_y, box_width, box_height, step_title, subtitle, fill)
        if index < box_count - 1:
            next_x = 12 + (index + 1) * (box_width + gap)
            add_arrow(drawing, x + box_width, box_y + box_height / 2, next_x, box_y + box_height / 2, "")

    if note:
        drawing.add(String(12, 14, note, fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#475569")))

    return drawing


def install_diagram() -> Drawing:
    return workflow_diagram(
        "Installazione - dal pacchetto al servizio",
        [
            ("Git/archivio", "sorgenti", "#ffffff"),
            ("install.sh", "dipendenze", "#e8f1fb"),
            ("/opt + venv", "app isolata", "#eaf7ef"),
            ("systemd", "avvio boot", "#ffffff"),
        ],
        "portal.env viene conservato durante reinstallazioni e aggiornamenti.",
    )


def provisioning_diagram() -> Drawing:
    return workflow_diagram(
        "Salva e connetti - cosa succede dietro il form",
        [
            ("Form", "SSID e sicurezza", "#ffffff"),
            ("NetworkManager", "profilo Wi-Fi", "#e8f1fb"),
            ("Tentativo", "rete finale", "#eaf7ef"),
            ("Esito", "ok o recovery", "#ffffff"),
        ],
        "Con due radio l'hotspot puo' restare attivo durante il tentativo.",
    )


def recovery_diagram() -> Drawing:
    return workflow_diagram(
        "Pi-Setup automatico - accesso disponibile e recovery",
        [
            ("Controllo", "Wi-Fi e LAN", "#ffffff"),
            ("Stabilita'", "30 s / 120 s", "#e8f1fb"),
            ("Accesso ok", "spegni hotspot", "#eaf7ef"),
            ("Nessun accesso", "attiva Pi-Setup", "#fff7ed"),
        ],
        "Con la sola wlan0, le reti salvate vengono riprovate ogni 5 minuti.",
    )


def ip_management_diagram() -> Drawing:
    return workflow_diagram(
        "Interfacce di rete e indirizzi IP",
        [
            ("Telefono", "Pi-Setup", "#ffffff"),
            ("Portale", "sezione IP", "#e8f1fb"),
            ("eth0/wlan", "DHCP o statico", "#eaf7ef"),
            ("nmcli", "applica profilo", "#ffffff"),
        ],
        "L'interfaccia che serve l'hotspot attivo viene protetta per non perdere il portale.",
    )


def access_sheet_diagram() -> Drawing:
    return workflow_diagram(
        "Documenti utente - PDF diretto e collegamenti cliccabili",
        [
            ("Guida/Scheda", "istruzioni e accesso", "#ffffff"),
            ("Scarica PDF", "impaginazione A4", "#e8f1fb"),
            ("Consegna", "utente autorizzato", "#fff7ed"),
            ("Setup", "configura rete", "#eaf7ef"),
        ],
        "La scheda contiene credenziali, link e QR cliccabili del portale.",
    )


def troubleshooting_diagram() -> Drawing:
    return workflow_diagram(
        "Risoluzione problemi - ordine consigliato",
        [
            ("SSID", "rete corretta", "#ffffff"),
            ("Servizio", "systemctl", "#e8f1fb"),
            ("Log", "journalctl", "#fff7ed"),
            ("Ritenta", "recovery", "#eaf7ef"),
        ],
        "Parti dai controlli semplici, poi passa ai log NetworkManager/servizio.",
    )


def wifi_scenario_diagram(two_interfaces: bool) -> Drawing:
    width = 16.0 * cm
    height = 5.3 * cm
    drawing = Drawing(width, height)

    drawing.add(Rect(0, 0, width, height, rx=10, ry=10, fillColor=colors.HexColor("#f8fbff"), strokeColor=colors.HexColor("#c8d7ea"), strokeWidth=0.8))

    if two_interfaces:
        drawing.add(String(12, height - 20, "Scenario B - Wi-Fi integrata + dongle USB", fontName="Helvetica-Bold", fontSize=10, fillColor=colors.HexColor("#14532d")))
        add_box(drawing, 18, 68, 105, 46, "Telefono", "browser portale", "#ffffff")
        add_box(drawing, 176, 84, 118, 42, "wlan0", "hotspot Pi-Setup", "#e8f1fb")
        add_box(drawing, 176, 30, 118, 42, "wlan1", "client Wi-Fi", "#eaf7ef")
        add_box(drawing, 350, 30, 95, 42, "Rete finale", "azienda/casa", "#ffffff")
        add_arrow(drawing, 123, 91, 176, 105, "setup")
        add_arrow(drawing, 294, 51, 350, 51, "connessione")
        drawing.add(String(18, 12, "Il portale resta disponibile mentre l'altra radio prova la rete finale.", fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#475569")))
    else:
        drawing.add(String(12, height - 20, "Scenario A - sola Wi-Fi integrata", fontName="Helvetica-Bold", fontSize=10, fillColor=colors.HexColor("#14532d")))
        add_box(drawing, 18, 66, 105, 46, "Telefono", "browser portale", "#ffffff")
        add_box(drawing, 176, 66, 124, 46, "wlan0", "hotspot poi client", "#e8f1fb")
        add_box(drawing, 360, 66, 95, 46, "Rete finale", "azienda/casa", "#ffffff")
        add_arrow(drawing, 123, 89, 176, 89, "setup")
        add_arrow(drawing, 300, 89, 360, 89, "dopo salva")
        drawing.add(String(18, 22, "Durante il tentativo il telefono puo' perdere Pi-Setup; se fallisce, il recovery lo riapre.", fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#475569")))

    return drawing


def wifi_scenario_flowables() -> list[object]:
    return [
        Spacer(1, 0.08 * cm),
        wifi_scenario_diagram(two_interfaces=False),
        Spacer(1, 0.18 * cm),
        wifi_scenario_diagram(two_interfaces=True),
        Spacer(1, 0.2 * cm),
    ]


def tcp_status_diagram() -> Drawing:
    width = 16.0 * cm
    height = 4.2 * cm
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, rx=10, ry=10, fillColor=colors.HexColor("#f8fbff"), strokeColor=colors.HexColor("#c8d7ea"), strokeWidth=0.8))
    drawing.add(String(12, height - 20, "Riepilogo rete locale", fontName="Helvetica-Bold", fontSize=10, fillColor=colors.HexColor("#14532d")))
    add_box(drawing, 18, 44, 128, 46, "VT Network Manager", "127.0.0.1:6001", "#e8f1fb")
    add_box(drawing, 326, 44, 128, 46, "Software display", "client TCP locale", "#eaf7ef")
    add_arrow(drawing, 146, 67, 326, 67, "subito + ogni 30 s")
    drawing.add(String(18, 20, "Una riga UTF-8 terminata da newline; servizio di sola lettura e non esposto sulla LAN.", fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#475569")))
    return drawing


def build_story():
    styles = build_styles()
    story = []

    story.append(Spacer(1, 2.2 * cm))
    story.append(Paragraph("Manuale Utente", styles["TitlePage"]))
    story.append(Paragraph("VT Network Manager", styles["TitlePage"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            "Installazione, configurazione e utilizzo del portale di rete per display a LED",
            styles["SmallMuted"],
        )
    )
    story.append(Spacer(1, 1.0 * cm))

    info_table = Table(
        [
            ["Versione documento", DOCUMENT_VERSION],
            ["Data", DOCUMENT_DATE],
            ["Target", "Controller del display con Raspberry Pi OS"],
            ["Ambito", "Setup Wi-Fi locale con supporto base 802.1X"],
        ],
        colWidths=[5.0 * cm, 8.5 * cm],
    )
    info_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f1fb")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#bfd3e6")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d3e1ef")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#10243d")),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEADING", (0, 0), (-1, -1), 13),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(info_table)
    story.append(PageBreak())

    in_code_block = False
    code_block_lines: list[str] = []

    for raw_line in SOURCE.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()

        if line.startswith("```"):
            in_code_block = not in_code_block
            if not in_code_block and code_block_lines:
                story.append(Preformatted(wrap_code_block(code_block_lines), styles["CodeBlock"]))
                story.append(Spacer(1, 0.08 * cm))
                code_block_lines = []
            continue

        if in_code_block:
            code_block_lines.append(line or " ")
            continue

        if not line.strip():
            story.append(Spacer(1, 0.12 * cm))
            continue

        if line.startswith("# "):
            continue

        if line.startswith("## "):
            story.append(Paragraph(apply_inline_markup(line[3:]), styles["SectionHeading"]))
            if line.startswith("## 8. "):
                story.append(Spacer(1, 0.08 * cm))
                story.append(provisioning_diagram())
                story.append(Spacer(1, 0.18 * cm))
            if line.startswith("## 10. "):
                story.append(Spacer(1, 0.08 * cm))
                story.append(troubleshooting_diagram())
                story.append(Spacer(1, 0.18 * cm))
            continue

        if line.startswith("### "):
            story.append(Paragraph(apply_inline_markup(line[4:]), styles["SubHeading"]))
            if line.startswith("### 5.0 "):
                story.append(Spacer(1, 0.08 * cm))
                story.append(install_diagram())
                story.append(Spacer(1, 0.18 * cm))
            if line.startswith("### 6.2 "):
                story.extend(wifi_scenario_flowables())
            if line.startswith("### 6.5 "):
                story.append(Spacer(1, 0.08 * cm))
                story.append(recovery_diagram())
                story.append(Spacer(1, 0.18 * cm))
            if line.startswith("### 6.7 "):
                story.append(Spacer(1, 0.08 * cm))
                story.append(ip_management_diagram())
                story.append(Spacer(1, 0.18 * cm))
            if line.startswith("### 6.8 "):
                story.append(Spacer(1, 0.08 * cm))
                story.append(tcp_status_diagram())
                story.append(Spacer(1, 0.18 * cm))
            if line.startswith("### 7.3 "):
                story.append(Spacer(1, 0.08 * cm))
                story.append(access_sheet_diagram())
                story.append(Spacer(1, 0.18 * cm))
            continue

        if line.startswith("- "):
            story.append(Paragraph(apply_inline_markup(line[2:]), styles["BulletCustom"], bulletText="-"))
            continue

        if len(line) > 2 and line.split(".", 1)[0].isdigit() and line[line.find(".") + 1 : line.find(".") + 2] == " ":
            story.append(Paragraph(apply_inline_markup(line), styles["BodyTextCustom"]))
            continue

        story.append(Paragraph(apply_inline_markup(line), styles["BodyTextCustom"]))

    return story


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.drawString(doc.leftMargin, 1.2 * cm, "VT Network Manager")
    canvas.drawRightString(A4[0] - doc.rightMargin, 1.2 * cm, f"Pagina {doc.page}")
    canvas.restoreState()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.8 * cm,
        title="Manuale Utente - VT Network Manager",
        author="OpenAI Codex",
    )
    story = build_story()
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    DOCS_PDF.write_bytes(OUTPUT_PDF.read_bytes())
    print(OUTPUT_PDF)


if __name__ == "__main__":
    main()
