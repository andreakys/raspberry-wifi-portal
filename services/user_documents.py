from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


INK = colors.HexColor("#14213d")
MUTED = colors.HexColor("#52647e")
BLUE = colors.HexColor("#0b6fb8")
GREEN = colors.HexColor("#16845b")
LINE = colors.HexColor("#c8d7ea")
PALE_BLUE = colors.HexColor("#eef5fc")
PALE_GREEN = colors.HexColor("#edf8f2")
PALE_ORANGE = colors.HexColor("#fff6e8")
WHITE = colors.white


def _qr_drawing(value: str, size: float) -> Drawing:
    widget = QrCodeWidget(value)
    x1, y1, x2, y2 = widget.getBounds()
    width = x2 - x1
    height = y2 - y1
    scale = min(size / width, size / height)
    drawing = Drawing(
        size,
        size,
        transform=[scale, 0, 0, scale, -x1 * scale, -y1 * scale],
    )
    drawing.add(widget)
    return drawing


class LinkedQrCode(Flowable):
    def __init__(self, value: str, size: float = 42 * mm) -> None:
        super().__init__()
        self.value = value
        self.width = size
        self.height = size

    def draw(self) -> None:
        renderPDF.draw(_qr_drawing(self.value, self.width), self.canv, 0, 0)
        self.canv.linkURL(
            self.value,
            (0, 0, self.width, self.height),
            relative=1,
            thickness=0,
        )


def build_portal_qr_svg(portal_url: str) -> bytes:
    rendered = renderSVG.drawToString(_qr_drawing(portal_url, 220))
    if isinstance(rendered, bytes):
        return rendered
    return rendered.encode("utf-8")


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "DocumentEyebrow",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=BLUE,
            spaceAfter=5,
        ),
        "title": ParagraphStyle(
            "DocumentTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            textColor=INK,
            alignment=0,
            spaceAfter=6,
        ),
        "intro": ParagraphStyle(
            "DocumentIntro",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=MUTED,
            spaceAfter=12,
        ),
        "heading": ParagraphStyle(
            "DocumentHeading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=INK,
            spaceBefore=10,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "DocumentBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=INK,
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "DocumentSmall",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=11,
            textColor=MUTED,
        ),
        "card_label": ParagraphStyle(
            "DocumentCardLabel",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=9,
            textColor=MUTED,
            spaceAfter=3,
        ),
        "card_value": ParagraphStyle(
            "DocumentCardValue",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=INK,
        ),
        "qr_title": ParagraphStyle(
            "DocumentQrTitle",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=INK,
            alignment=TA_CENTER,
            spaceAfter=5,
        ),
        "qr_caption": ParagraphStyle(
            "DocumentQrCaption",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def _safe(value: object) -> str:
    return escape(str(value))


def _link(url: str, label: str | None = None) -> str:
    return (
        f"<link href='{_safe(url)}' color='#0b6fb8'>"
        f"<u>{_safe(label or url)}</u></link>"
    )


def _document_footer(canvas, document, app_version: str, document_name: str) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(18 * mm, 9.5 * mm, f"{document_name} - versione {app_version}")
    canvas.drawRightString(
        A4[0] - 18 * mm,
        9.5 * mm,
        f"Pagina {document.page}",
    )
    canvas.restoreState()


def _pdf_document(
    title: str,
    app_version: str,
    document_name: str,
) -> tuple[BytesIO, SimpleDocTemplate]:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=20 * mm,
        title=title,
        author="VT Network Manager",
        subject=document_name,
    )
    return buffer, document


def _build_pdf(
    story: list[Flowable],
    title: str,
    app_version: str,
    document_name: str,
) -> bytes:
    buffer, document = _pdf_document(title, app_version, document_name)

    def footer(canvas, doc) -> None:
        _document_footer(canvas, doc, app_version, document_name)

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def _credentials_table(
    access_data: dict[str, str],
    styles: dict[str, ParagraphStyle],
) -> Table:
    rows = [
        (
            "HOTSPOT TEMPORANEO",
            _safe(access_data["hotspot_ssid"]),
            "PASSWORD HOTSPOT",
            _safe(access_data["hotspot_password"]),
        ),
        (
            "INDIRIZZO PORTALE",
            _link(access_data["portal_url"]),
            "PASSWORD PORTALE",
            _safe(access_data["portal_password"]),
        ),
    ]
    data: list[list[Paragraph]] = []
    for left_label, left_value, right_label, right_value in rows:
        data.append(
            [
                Paragraph(
                    f"<font color='#52647e' size='7'>{left_label}</font><br/>"
                    f"<b>{left_value}</b>",
                    styles["card_value"],
                ),
                Paragraph(
                    f"<font color='#52647e' size='7'>{right_label}</font><br/>"
                    f"<b>{right_value}</b>",
                    styles["card_value"],
                ),
            ]
        )

    table = Table(data, colWidths=[83 * mm, 83 * mm], rowHeights=[25 * mm, 25 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.7, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def build_access_sheet_pdf(
    page_title: str,
    app_version: str,
    access_data: dict[str, str],
) -> bytes:
    styles = _styles()
    portal_url = access_data["portal_url"]
    story: list[Flowable] = [
        Paragraph("DATI RISERVATI DI ACCESSO", styles["eyebrow"]),
        Paragraph(f"Scheda accesso - {_safe(page_title)}", styles["title"]),
        Paragraph(
            "Usa questa scheda per collegarti all'hotspot temporaneo e aprire il portale di configurazione del display.",
            styles["intro"],
        ),
        _credentials_table(access_data, styles),
        Spacer(1, 8 * mm),
    ]

    qr_panel = Table(
        [
            [
                LinkedQrCode(portal_url, 40 * mm),
                [
                    Paragraph("Apri il portale", styles["heading"]),
                    Paragraph(
                        "Dopo esserti collegato a <b>"
                        f"{_safe(access_data['hotspot_ssid'])}</b>, inquadra o tocca il QR.",
                        styles["body"],
                    ),
                    Paragraph(_link(portal_url), styles["body"]),
                    Paragraph(
                        "Il QR e il collegamento sono cliccabili anche nel PDF.",
                        styles["small"],
                    ),
                ],
            ]
        ],
        colWidths=[50 * mm, 116 * mm],
    )
    qr_panel.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_GREEN),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend(
        [
            qr_panel,
            Spacer(1, 5 * mm),
            Paragraph("Procedura rapida", styles["heading"]),
            Paragraph(
                "<b>1.</b> Collega telefono o PC alla rete Wi-Fi indicata come hotspot temporaneo.",
                styles["body"],
            ),
            Paragraph(
                "<b>2.</b> Apri il QR oppure digita l'indirizzo del portale nel browser.",
                styles["body"],
            ),
            Paragraph(
                "<b>3.</b> Inserisci la password portale e configura LAN o collegamento Wi-Fi.",
                styles["body"],
            ),
        ]
    )

    security_note = Table(
        [
            [
                Paragraph(
                    "<b>Conservazione sicura.</b> Questa pagina contiene password operative. "
                    "Condividila solo con personale autorizzato e rigenerala quando le credenziali cambiano.",
                    styles["body"],
                )
            ]
        ],
        colWidths=[166 * mm],
    )
    security_note.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_ORANGE),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#e6b866")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([Spacer(1, 4 * mm), security_note])
    return _build_pdf(
        story,
        f"Scheda accesso - {page_title}",
        app_version,
        "Scheda accesso",
    )


def _numbered_step(
    number: int,
    title: str,
    body: str,
    styles: dict[str, ParagraphStyle],
) -> Table:
    number_cell = Paragraph(
        f"<font color='#ffffff'><b>{number}</b></font>",
        ParagraphStyle(
            f"StepNumber{number}",
            parent=styles["body"],
            alignment=TA_CENTER,
            leading=18,
        ),
    )
    content = Paragraph(f"<b>{title}</b><br/>{body}", styles["body"])
    table = Table([[number_cell, content]], colWidths=[10 * mm, 154 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), BLUE),
                ("BACKGROUND", (1, 0), (1, 0), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 2),
                ("RIGHTPADDING", (0, 0), (0, 0), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (1, 0), (1, 0), 9),
                ("RIGHTPADDING", (1, 0), (1, 0), 9),
            ]
        )
    )
    return table


def _rule_box(
    title: str,
    text: str,
    styles: dict[str, ParagraphStyle],
    background=PALE_GREEN,
) -> Table:
    table = Table(
        [[Paragraph(f"<b>{title}</b><br/>{text}", styles["body"])]],
        colWidths=[164 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def build_quick_guide_pdf(
    page_title: str,
    app_version: str,
    access_data: dict[str, str],
) -> bytes:
    styles = _styles()
    portal_url = access_data["portal_url"]
    story: list[Flowable] = [
        Paragraph("GUIDA RAPIDA CONFIGURAZIONE", styles["eyebrow"]),
        Paragraph(_safe(page_title), styles["title"]),
        Paragraph(
            "Procedura essenziale per configurare LAN, Wi-Fi e indirizzi IP del display. "
            "La guida contiene regole operative stabili e non riporta valori di stato momentanei.",
            styles["intro"],
        ),
    ]

    start_panel = Table(
        [
            [
                LinkedQrCode(portal_url, 34 * mm),
                [
                    Paragraph("Collegamento iniziale", styles["heading"]),
                    Paragraph(
                        f"1. Collegati a <b>{_safe(access_data['hotspot_ssid'])}</b>.<br/>"
                        f"2. Apri {_link(portal_url)}.<br/>"
                        "3. Accedi con la password riportata nella scheda accesso.",
                        styles["body"],
                    ),
                    Paragraph(
                        "Il QR apre il portale dopo il collegamento all'hotspot.",
                        styles["small"],
                    ),
                ],
            ]
        ],
        colWidths=[44 * mm, 122 * mm],
    )
    start_panel.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_GREEN),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend(
        [
            start_panel,
            Spacer(1, 5 * mm),
            Paragraph("Scegli il percorso di configurazione", styles["heading"]),
            _numbered_step(
                1,
                "LAN cablata",
                "Usa la sezione <b>Interfacce di rete e indirizzi IP</b> per impostare eth0 in DHCP o con indirizzo statico.",
                styles,
            ),
            Spacer(1, 2.5 * mm),
            _numbered_step(
                2,
                "Collegamento Wi-Fi",
                "Usa <b>Configura collegamento Wi-Fi</b>, seleziona la radio, scansiona le reti e salva il profilo.",
                styles,
            ),
            Spacer(1, 5 * mm),
            Paragraph("Radio Wi-Fi: regola semplice", styles["heading"]),
            _rule_box(
                "wlan0 integrata",
                "E' sempre la radio presente sulla scheda. Se non c'e' un dongle USB, gestisce sia Pi-Setup sia la connessione Wi-Fi finale.",
                styles,
            ),
            Spacer(1, 2.5 * mm),
            _rule_box(
                "wlan1 dongle USB",
                "Compare solo quando il dongle e' collegato. Con due radio, wlan0 mantiene Pi-Setup e wlan1 viene preferita automaticamente per scansione e connessione finale.",
                styles,
                PALE_BLUE,
            ),
            PageBreak(),
            Paragraph("CONFIGURAZIONE RETE", styles["eyebrow"]),
            Paragraph("LAN cablata e indirizzi IP", styles["title"]),
            Paragraph(
                "La LAN puo' essere configurata anche mentre il portale e' aperto tramite Pi-Setup.",
                styles["intro"],
            ),
            _numbered_step(
                1,
                "Seleziona eth0",
                "Apri <b>Interfacce di rete e indirizzi IP</b> e scegli l'interfaccia Ethernet.",
                styles,
            ),
            Spacer(1, 2.5 * mm),
            _numbered_step(
                2,
                "Scegli la modalita' IPv4",
                "Con <b>DHCP automatico</b> il router assegna i dati. Con <b>Indirizzo statico</b> inserisci indirizzo/prefisso, gateway e DNS.",
                styles,
            ),
            Spacer(1, 2.5 * mm),
            _numbered_step(
                3,
                "Applica e verifica",
                "Premi <b>Applica configurazione IP</b>. Il collegamento puo' interrompersi se l'indirizzo cambia: riapri il portale usando il nuovo IP.",
                styles,
            ),
            Spacer(1, 6 * mm),
            Paragraph("Configurazione Wi-Fi", styles["title"]),
            _numbered_step(
                1,
                "Controlla la radio",
                "Con il dongle presente usa wlan1. Senza dongle viene usata wlan0.",
                styles,
            ),
            Spacer(1, 2.5 * mm),
            _numbered_step(
                2,
                "Scansiona e seleziona",
                "Premi <b>Scansiona reti</b> e scegli l'SSID dall'elenco. Le reti meno forti restano disponibili nello scorrimento.",
                styles,
            ),
            Spacer(1, 2.5 * mm),
            _numbered_step(
                3,
                "Inserisci le credenziali",
                "Controlla sicurezza e password. Usa <b>Mostra</b> per evitare errori di battitura.",
                styles,
            ),
            Spacer(1, 2.5 * mm),
            _numbered_step(
                4,
                "Salva e connetti",
                "Il portale crea un profilo gestito. Con la sola wlan0 il telefono puo' perdere temporaneamente Pi-Setup durante il tentativo.",
                styles,
            ),
            PageBreak(),
            Paragraph("GESTIONE E RECOVERY", styles["eyebrow"]),
            Paragraph("Come si comporta Pi-Setup", styles["title"]),
            Paragraph(
                "Pi-Setup e' un accesso temporaneo di configurazione. Il servizio lo gestisce automaticamente per mantenere il display raggiungibile senza lasciare una radio accesa inutilmente.",
                styles["intro"],
            ),
            _rule_box(
                "Con due radio",
                "La connessione finale usa wlan1. Quando il client Wi-Fi e' stabile, Pi-Setup su wlan0 viene disattivato automaticamente; in assenza di accesso viene ripristinato.",
                styles,
            ),
            Spacer(1, 2.5 * mm),
            _rule_box(
                "Con la sola wlan0",
                "Hotspot e client condividono la stessa radio. Se esiste una rete salvata, il servizio effettua tentativi controllati e riattiva subito Pi-Setup quando la connessione non riesce.",
                styles,
                PALE_BLUE,
            ),
            Spacer(1, 2.5 * mm),
            _rule_box(
                "Con LAN disponibile",
                "Dopo una connessione cablata stabile Pi-Setup puo' essere disattivato. Se la LAN viene persa e non esiste un altro accesso, il recovery lo riattiva.",
                styles,
                PALE_ORANGE,
            ),
            Spacer(1, 6 * mm),
            Paragraph("Profili salvati", styles["heading"]),
            Paragraph(
                "In <b>Connessioni salvate dal portale</b> puoi eliminare vecchi profili Wi-Fi o LAN e crearne di nuovi. "
                "L'hotspot temporaneo e i profili di sistema restano protetti.",
                styles["body"],
            ),
            Paragraph("Controlli finali", styles["heading"]),
            Paragraph(
                "1. Verifica l'indirizzo di eth0 o della radio client nella sezione interfacce.<br/>"
                "2. Controlla che la connettivita' risulti disponibile.<br/>"
                "3. Prova a riaprire il portale dall'indirizzo della LAN o della rete Wi-Fi definitiva.<br/>"
                "4. Conserva la scheda accesso separatamente: contiene le password operative.",
                styles["body"],
            ),
        ]
    )
    return _build_pdf(
        story,
        f"Guida rapida - {page_title}",
        app_version,
        "Guida rapida",
    )
