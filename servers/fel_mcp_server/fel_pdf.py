"""
FEL -> Branded PDF renderer (ReportLab)
- Parses FEL XML (SAT Guatemala)
- Validates totals (subtotal, VAT 12%, total)
- Composes a branded PDF (logo, fonts, colors)
- Builds SAT verification URL/QR
"""

import os
import sys
import xml.etree.ElementTree as ET
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Spacer, Paragraph
from reportlab.graphics.shapes import Drawing, Group
from reportlab.graphics.barcode import qr
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER

from config import (
    ORANGE, DARK_GRAY, BLACK, WHITE, GRAY_LIGHT, GRAY_SOFT,
    DEFAULT_QR_SIZE, DEFAULT_TOP_BAR_HEIGHT,
    XML_PATH, LOGO_PATH, OUTPUT_PDF,
    ACTIVE_FONT, THEME, WEBSITE, PHONE, EMAIL,
    GLOBAL_FONT_SIZE, LOGO_WIDTH, LOGO_HEIGHT, FONTS
)

# =========================
# Font & style registration
# =========================
def registerActiveFonts() -> str:
    """
    Register active TTF fonts in ReportLab based on FEL_ACTIVE_FONT.
    Returns the base font family name for later use in styles.
    """
    font = FONTS[ACTIVE_FONT]
    base = font["name"]
    for style, filename in font["files"].items():
        ttf_path = os.path.join(font["path"], filename)
        pdfmetrics.registerFont(TTFont(f"{base}-{style}", ttf_path))
    return base


def getStyles(baseFont: str):
    """
    Build global paragraph styles with brand fonts/colors.
    """
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = f"{baseFont}-Regular"
    styles["Normal"].fontSize = GLOBAL_FONT_SIZE

    styles.add(ParagraphStyle(
        name="InvoiceTitle",
        fontName=f"{baseFont}-Bold",
        fontSize=24,
        leading=20,
        spaceAfter=10,
        textColor=DARK_GRAY
    ))
    styles.add(ParagraphStyle(
        name="Subtitle",
        fontName=f"{baseFont}-SemiBold",
        fontSize=12,
        textColor=DARK_GRAY
    ))
    styles.add(ParagraphStyle(
        name="ItalicSmall",
        fontName=f"{baseFont}-Italic",
        fontSize=10,
        textColor=GRAY_SOFT
    ))
    return styles


# ====================
# FEL XML read & utils
# ====================
def readFelXml(xmlPath: str) -> dict:
    """
    Parse a FEL XML and extract key fields for rendering and validation.
    NOTE: adjust XPath / namespaces to match your actual FEL XML structure.
    """
    if not os.path.exists(xmlPath):
        raise FileNotFoundError(f"XML not found: {xmlPath}")

    tree = ET.parse(xmlPath)
    root = tree.getroot()
    ns = {"dte": "http://www.sat.gob.gt/dte/fel/0.2.0"}

    fechaRaw = root.find(".//dte:DatosGenerales", ns).attrib["FechaHoraEmision"]
    yyyy, mm, dd = fechaRaw.split("T")[0].split("-")
    fecha = f"{dd}/{mm}/{yyyy}"

    moneda = root.find(".//dte:DatosGenerales", ns).attrib["CodigoMoneda"]

    data = {
        "serie": root.find(".//dte:NumeroAutorizacion", ns).attrib["Serie"],
        "numero_dte": root.find(".//dte:NumeroAutorizacion", ns).attrib["Numero"],
        "nombre": root.find(".//dte:Emisor", ns).attrib["NombreEmisor"],
        "nit": root.find(".//dte:Emisor", ns).attrib["NITEmisor"],
        "numero_autorizacion": root.find(".//dte:NumeroAutorizacion", ns).text,
        "nombre_receptor": root.find(".//dte:Receptor", ns).attrib["NombreReceptor"],
        "id_receptor": root.find(".//dte:Receptor", ns).attrib["IDReceptor"],
        "monto": root.find(".//dte:Precio", ns).text,
        "fecha_emision": fecha,
        "moneda": moneda,
        "item": {
            "descripcion": root.find(".//dte:Descripcion", ns).text,
            "cantidad": root.find(".//dte:Cantidad", ns).text,
            "precio_unitario": f'{float(root.find(".//dte:MontoGravable", ns).text):,.2f}',
            "total": f'{float(root.find(".//dte:MontoGravable", ns).text):,.2f}',
        },
        "subtotal": f'{float(root.find(".//dte:MontoGravable", ns).text):,.2f}',
        "iva": f'{float(root.find(".//dte:MontoImpuesto", ns).text):,.2f}',
        "total": f'{float(root.find(".//dte:GranTotal", ns).text):,.2f}',
    }
    return data


def buildSatVerificationUrl(data: dict) -> str:
    """
    Build SAT verification URL for the given FEL data.
    """
    base = "https://felpub.c.sat.gob.gt/verificador-web/publico/vistas/verificacionDte.jsf"
    return (
        f"{base}?tipo=autorizacion"
        f"&numero={data['numero_autorizacion']}"
        f"&emisor={data['nit']}"
        f"&receptor={data['id_receptor']}"
        f"&monto={data['monto']}"
    )


# ==============
# Canvas helpers
# ==============
def drawTopBar(canvas, doc, topBarHeight: int):
    canvas.setFillColor(DARK_GRAY)
    canvas.rect(0, doc.pagesize[1] - topBarHeight, doc.pagesize[0], topBarHeight, fill=1, stroke=0)


def drawBottomBar(canvas, doc):
    """
    Draws a split bottom bar (left gray / right orange) and prints contact info centered.
    """
    leftHeight  = 30
    rightHeight = 50
    y = 0
    iconSize = 14
    padIconText = 8
    fontSize = 10

    pageWidth = doc.pagesize[0]
    leftWidth = int(pageWidth * 0.55)
    rightWidth = pageWidth - leftWidth

    # Background blocks
    canvas.setFillColor(DARK_GRAY)
    canvas.rect(0, y, leftWidth, leftHeight, fill=1, stroke=0)
    canvas.setFillColor(ORANGE)
    canvas.rect(leftWidth, y, rightWidth, rightHeight, fill=1, stroke=0)

    # Left (Website)
    baseFont = FONTS[ACTIVE_FONT]["name"]
    canvas.setFont(f"{baseFont}-Regular", fontSize)
    canvas.setFillColor(GRAY_LIGHT)

    text = WEBSITE
    textWidth = canvas.stringWidth(text, f"{baseFont}-Regular", fontSize)
    contentWidth = iconSize + padIconText + textWidth
    startX = (leftWidth - contentWidth) // 2

    # Website icon (optional static asset)
    webIconPath = "./assets/images/icon_web2_white.png"
    if os.path.exists(webIconPath):
        webIcon = Image(webIconPath, width=iconSize, height=iconSize)
        webIcon.drawOn(canvas, startX, y + (leftHeight - iconSize) // 2)
    canvas.drawString(startX + iconSize + padIconText, y + leftHeight // 2 - fontSize // 2 + 1, text)

    # Right (Phone + Email)
    canvas.setFont(f"{baseFont}-Regular", 9)
    canvas.setFillColor(BLACK)
    maxTextWidth = max(
        canvas.stringWidth(PHONE, f"{baseFont}-Regular", 9),
        canvas.stringWidth(EMAIL, f"{baseFont}-Regular", 9)
    )
    contentRightWidth = iconSize + padIconText + maxTextWidth
    xRight = leftWidth + (rightWidth - contentRightWidth) // 2
    lineSpacing = 4
    contentHeight = 2 * iconSize + lineSpacing
    yRight = y + (rightHeight - contentHeight) // 2

    phoneIconPath = "./assets/images/phone.png"
    if os.path.exists(phoneIconPath):
        phoneIcon = Image(phoneIconPath, width=iconSize, height=iconSize)
        phoneIcon.drawOn(canvas, xRight, yRight + iconSize + lineSpacing)
    canvas.drawString(xRight + iconSize + padIconText, yRight + iconSize + lineSpacing + 1, PHONE)

    emailIconPath = "./assets/images/email.png"
    if os.path.exists(emailIconPath):
        emailIcon = Image(emailIconPath, width=iconSize, height=iconSize)
        emailIcon.drawOn(canvas, xRight, yRight)
    canvas.drawString(xRight + iconSize + padIconText, yRight + 1, EMAIL)


def drawBars(canvas, doc):
    drawTopBar(canvas, doc, DEFAULT_TOP_BAR_HEIGHT)
    drawBottomBar(canvas, doc)


# ===========================
# Flowables (header/blocks/qr)
# ===========================
def buildHeader(logoPath: str, emitterData: dict, styles):
    """
    Header with logo at left and emitter fields at right (single-line fields).
    """
    baseFont = FONTS[ACTIVE_FONT]["name"]
    rightStyle = ParagraphStyle(
        name="RightRow",
        fontName=f"{baseFont}-Regular",
        fontSize=GLOBAL_FONT_SIZE,
        textColor=BLACK,
        alignment=TA_RIGHT,
        leading=15,
    )

    logo = Image(logoPath, width=LOGO_WIDTH, height=LOGO_HEIGHT) if os.path.exists(logoPath) else Paragraph("", styles["Normal"])
    rows = [
        Paragraph(f'<font name="{baseFont}-Bold">Series:</font> {emitterData["serie"]}', rightStyle),
        Paragraph(f'<font name="{baseFont}-Bold">DTE Number:</font> {emitterData["numero_dte"]}', rightStyle),
        Paragraph(f'<font name="{baseFont}-Bold">Name:</font> {emitterData["nombre"]}', rightStyle),
        Paragraph(f'<font name="{baseFont}-Bold">NIT:</font> {emitterData["nit"]}', rightStyle),
    ]

    rightTable = Table([[r] for r in rows], colWidths=[360])
    rightTable.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 120),
        ("RIGHTPADDING", (0, 0), (-1, -1), 15),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    table = Table([[logo, rightTable]], colWidths=[LOGO_WIDTH + 20, 380])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 15),
        ("LEFTPADDING", (1, 0), (1, 0), 30),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return table


def buildReceiverBlock(data: dict, styles):
    baseFont = FONTS[ACTIVE_FONT]["name"]
    leftStyle = ParagraphStyle(
        name="LeftRow",
        fontName=f"{baseFont}-Regular",
        fontSize=GLOBAL_FONT_SIZE,
        textColor=BLACK,
        alignment=TA_LEFT,
        leading=15,
    )

    rows = [
        Paragraph(f'<font name="{baseFont}-Bold">Receiver:</font> {data["nombre_receptor"]}', leftStyle),
        Paragraph(f'<font name="{baseFont}-Bold">Receiver NIT:</font> {data["id_receptor"]}', leftStyle),
    ]

    t = Table([[r] for r in rows], colWidths=[460])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), -15),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def buildDateCurrencyBlock(data: dict, styles):
    baseFont = FONTS[ACTIVE_FONT]["name"]
    st = ParagraphStyle(
        name="DateCurrency",
        fontName=f"{baseFont}-Regular",
        fontSize=GLOBAL_FONT_SIZE,
        textColor=BLACK,
        alignment=TA_LEFT,
        leading=15,
    )

    rows = [
        Paragraph(f'<font name="{baseFont}-Bold">Date:</font> {data["fecha_emision"]}', st),
        Paragraph(f'<font name="{baseFont}-Bold">Currency:</font> {data["moneda"]}', st),
    ]

    t = Table([[r] for r in rows], colWidths=[460])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), -15),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def buildItemsAndTotalsBlock(data: dict, styles):
    baseFont = FONTS[ACTIVE_FONT]["name"]

    thStyle = ParagraphStyle(name="Th", fontName=f"{baseFont}-SemiBold", fontSize=GLOBAL_FONT_SIZE, alignment=TA_CENTER, textColor=WHITE)
    cellLeft  = ParagraphStyle(name="CellLeft",  fontName=f"{baseFont}-Regular",  fontSize=GLOBAL_FONT_SIZE, alignment=TA_LEFT)
    cellMid   = ParagraphStyle(name="CellMid",   fontName=f"{baseFont}-Regular",  fontSize=GLOBAL_FONT_SIZE, alignment=TA_CENTER)
    cellRight = ParagraphStyle(name="CellRight", fontName=f"{baseFont}-Regular",  fontSize=GLOBAL_FONT_SIZE, alignment=TA_CENTER)
    cellRightBold = ParagraphStyle(name="CellRightBold", fontName=f"{baseFont}-Bold", fontSize=GLOBAL_FONT_SIZE, alignment=TA_RIGHT)

    item = data["item"]
    subtotal = data["subtotal"]
    iva = data["iva"]
    total = data["total"]

    itemsTable = Table([
        [
            Paragraph("Concept", thStyle),
            Paragraph("Qty", thStyle),
            Paragraph("Unit Price (Q)", thStyle),
            Paragraph("Total (Q)", thStyle)
        ],
        [
            Paragraph(item["descripcion"], cellLeft),
            Paragraph(item["cantidad"], cellMid),
            Paragraph(item["precio_unitario"], cellMid),
            Paragraph(item["total"], cellMid)
        ]
    ], colWidths=[260, 60, 90, 90])
    itemsTable.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK_GRAY),
        ("TEXTCOLOR",  (0, 0), (-1, 0), WHITE),
        ("LINEBELOW",  (0, 1), (-1, 1), 1, BLACK),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("VALIGN", (1, 1), (3, 1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))

    summaryData = [
        ["", "", Paragraph("Subtotal", cellMid), Paragraph(subtotal, cellRight)],
        ["", "", Paragraph("VAT 12 %", cellMid), Paragraph(iva,      cellRight)],
        ["", "", Paragraph('<font name="%s-Bold">Total</font>' % baseFont, cellMid), Paragraph(total, cellRight)],
    ]
    summaryTable = Table(summaryData, colWidths=[260, 60, 90, 90])
    summaryTable.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))

    payStyle = ParagraphStyle(
        name="PayInfo",
        fontName=f"{baseFont}-Regular",
        fontSize=GLOBAL_FONT_SIZE,
        textColor=BLACK,
        alignment=TA_LEFT,
        leading=14
    )
    payInfo = Paragraph(f'<font name="{baseFont}-Bold">Payment method:</font> Transfer', payStyle)
    payTable = Table([[payInfo]], colWidths=[460])
    payTable.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), -10),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    return [itemsTable, Spacer(1, 10), summaryTable, Spacer(1, 10), payTable]


def buildFooterQr(data: dict, qrUrl: str, qrSize: int):
    """
    Footer with QR (no border) and verification/authority lines.
    """
    baseFont = FONTS[ACTIVE_FONT]["name"]
    qrCode = qr.QrCodeWidget(qrUrl)
    bounds = qrCode.getBounds()
    scaleX = qrSize / (bounds[2] - bounds[0])
    scaleY = qrSize / (bounds[3] - bounds[1])
    group = Group(qrCode)
    group.scale(scaleX, scaleY)
    drawing = Drawing(qrSize, qrSize)
    drawing.add(group)

    footerStyle = ParagraphStyle(
        name="FooterData",
        fontName=f"{baseFont}-Regular",
        fontSize=GLOBAL_FONT_SIZE,
        textColor=BLACK,
        alignment=TA_LEFT,
        leading=8
    )
    lines = [
        Paragraph("Subject to definitive ISR withholding.", footerStyle),
        Paragraph(f'<b>Authorization:</b> {data["numero_autorizacion"]}', footerStyle),
        Paragraph('<b>Certifier:</b> Superintendencia de Administración Tributaria', footerStyle),
        Paragraph('<b>NIT:</b> 16693949', footerStyle),  # ajusta si aplica
    ]
    textTable = Table([[ln] for ln in lines], colWidths=[340])
    textTable.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))

    table = Table([[drawing, textTable]], colWidths=[qrSize + 20, 360])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 15),
        ("LEFTPADDING", (1, 0), (1, 0), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


# ==============
# PDF generation
# ==============
def generatePdf(
    xmlPath: str = XML_PATH,
    logoPath: str = LOGO_PATH,
    outputPdf: str = OUTPUT_PDF,
    topBarHeight: int = DEFAULT_TOP_BAR_HEIGHT,
    qrSize: int = DEFAULT_QR_SIZE
):
    """
    High-level entrypoint:
      1) Read FEL XML
      2) Build verification URL
      3) Compose PDF with header/blocks/footer
    """
    baseFont = registerActiveFonts()
    styles = getStyles(baseFont)
    data = readFelXml(xmlPath)
    qrUrl = buildSatVerificationUrl(data)

    os.makedirs(os.path.dirname(outputPdf), exist_ok=True)
    doc = SimpleDocTemplate(
        outputPdf, pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )

    flow = []
    flow.append(Spacer(1, 30))
    flow.append(buildHeader(logoPath, data, styles))
    flow.append(Spacer(1, 50))
    flow.append(buildReceiverBlock(data, styles))
    flow.append(Spacer(1, 20))
    flow.append(buildDateCurrencyBlock(data, styles))
    flow.append(Spacer(1, 10))
    flow.extend(buildItemsAndTotalsBlock(data, styles))
    flow.append(Spacer(1, 50))
    flow.append(buildFooterQr(data, qrUrl, qrSize))

    # wrapper to pass topBarHeight
    def drawBars(c, d):
        drawTopBar(c, d, topBarHeight)
        drawBottomBar(c, d)

    doc.build(flow, onFirstPage=drawBars)
    sys.stderr.write(f"PDF generated: {outputPdf}\n")


if __name__ == "__main__":
    generatePdf()
