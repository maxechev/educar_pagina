from decimal import Decimal
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def formatear_moneda(valor):
    try:
        val = Decimal(str(valor))
        return f"${val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "$0,00"


def generar_factura_pdf(
    cuota,
    alumno,
    tutor,
    desglose_conceptos,
    numero_factura=None,
    fecha_emision=None,
):
    """
    Genera un archivo PDF formal con la liquidación/factura de aranceles mensuales.
    Retorna los bytes del PDF generado.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Estilos tipográficos
    style_header_title = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#1E3A8A"),
    )
    style_header_sub = ParagraphStyle(
        "HeaderSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )
    style_doc_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        alignment=2,  # Align Right
    )
    style_doc_info = ParagraphStyle(
        "DocInfo",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
        alignment=2,
    )
    style_section_title = ParagraphStyle(
        "SectionTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#1E3A8A"),
    )
    style_cell = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1E293B"),
    )
    style_cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0F172A"),
    )
    style_cell_right = ParagraphStyle(
        "CellRight",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1E293B"),
        alignment=2,
    )
    style_cell_right_bold = ParagraphStyle(
        "CellRightBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#1E3A8A"),
        alignment=2,
    )
    style_footer = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748B"),
        alignment=1,  # Center
    )

    story = []

    # 1. Cabecera Institucional
    num_factura = (
        numero_factura
        or f"FAC-{cuota.periodo[:3].upper()}-{cuota.id_cuota:05d}"
    )
    f_emision = fecha_emision or (
        cuota.fecha_vencimiento.strftime("%d/%m/%Y")
        if cuota.fecha_vencimiento
        else "-"
    )
    f_vto = (
        cuota.fecha_vencimiento.strftime("%d/%m/%Y")
        if cuota.fecha_vencimiento
        else "-"
    )

    header_left = [
        Paragraph("<b>CENTRO EDUCATIVO «TRANSFORMAR PARA EDUCAR»</b>", style_header_title),
        Paragraph("Educación Inicial • Primaria • Secundaria | DIEGEP N° 4582", style_header_sub),
        Paragraph("Av. San Martín 1234, Buenos Aires • Tel: (011) 4567-8900", style_header_sub),
        Paragraph("CUIT: 30-71234567-8 • IVA Exento", style_header_sub),
    ]

    header_right = [
        Paragraph("<b>LIQUIDACIÓN MENSUAL</b>", style_doc_title),
        Paragraph(f"<b>N° Comprobante:</b> {num_factura}", style_doc_info),
        Paragraph(f"<b>Período:</b> {cuota.periodo}", style_doc_info),
        Paragraph(f"<b>Fecha Emisión:</b> {f_emision}", style_doc_info),
        Paragraph(f"<b>Fecha Vencimiento:</b> {f_vto}", style_doc_info),
    ]

    header_table = Table(
        [[header_left, header_right]],
        colWidths=[320, 220],
    )
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceBefore=0, spaceAfter=10))

    # 2. Datos del Alumno y Tutor
    persona_alumno = getattr(alumno, "id_persona", None)
    nombre_alumno = (
        f"{persona_alumno.nombre} {persona_alumno.apellido}".strip()
        if persona_alumno
        else "Alumno"
    )
    curso = getattr(alumno, "id_curso", None)
    nombre_curso = (
        f"{curso.anio}° {curso.comision} - {curso.nivel_educativo.nombre}"
        if curso and curso.nivel_educativo
        else "No asignado"
    )

    persona_tutor = getattr(tutor, "id_persona", None)
    nombre_tutor = (
        f"{persona_tutor.nombre} {persona_tutor.apellido}".strip()
        if persona_tutor
        else "Tutor / Responsable"
    )
    dni_tutor = getattr(persona_tutor, "dni", "-") if persona_tutor else "-"
    email_tutor = (
        getattr(persona_tutor.id_usuario, "correo", "")
        if (persona_tutor and getattr(persona_tutor, "id_usuario", None))
        else getattr(tutor, "email_contacto", "-")
    ) or "-"

    info_data = [
        [
            Paragraph("<b>DATOS DEL ALUMNO</b>", style_section_title),
            Paragraph("<b>RESPONSABLE DE PAGO (TUTOR)</b>", style_section_title),
        ],
        [
            Paragraph(f"<b>Nombre:</b> {nombre_alumno}<br/><b>Legajo:</b> {alumno.legajo}<br/><b>Curso:</b> {nombre_curso}", style_cell),
            Paragraph(f"<b>Nombre:</b> {nombre_tutor}<br/><b>DNI:</b> {dni_tutor}<br/><b>Email:</b> {email_tutor}", style_cell),
        ],
    ]
    info_table = Table(info_data, colWidths=[270, 270])
    info_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(info_table)
    story.append(Spacer(1, 14))

    # 3. Detalle Discriminado de Conceptos
    story.append(Paragraph("<b>DETALLE DE CONCEPTOS ARANCELARIOS</b>", style_section_title))
    story.append(Spacer(1, 4))

    table_rows = [
        [
            Paragraph("<b>Item</b>", style_cell_bold),
            Paragraph("<b>Concepto</b>", style_cell_bold),
            Paragraph("<b>Importe</b>", style_cell_right_bold),
        ]
    ]

    total_calculado = Decimal("0")
    for idx, item in enumerate(desglose_conceptos, start=1):
        concepto = item.get("concepto", "Arancel")
        monto = Decimal(str(item.get("monto", "0")))
        total_calculado += monto
        table_rows.append([
            Paragraph(str(idx), style_cell),
            Paragraph(concepto, style_cell),
            Paragraph(formatear_moneda(monto), style_cell_right),
        ])

    table_rows.append([
        Paragraph("", style_cell),
        Paragraph("<b>TOTAL A ABONAR</b>", style_cell_bold),
        Paragraph(formatear_moneda(cuota.total_obligacion or total_calculado), style_cell_right_bold),
    ])

    conceptos_table = Table(table_rows, colWidths=[40, 360, 140])
    conceptos_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#CBD5E1")),
            ("LINEABOVE", (0, -1), (-1, -1), 1.5, colors.HexColor("#1E3A8A")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    # Re-apply text color to header cells
    for col in range(3):
        table_rows[0][col].style.textColor = colors.white

    story.append(conceptos_table)
    story.append(Spacer(1, 16))

    # 4. Datos de Pago por Transferencia
    pago_box_data = [
        [
            Paragraph("<b>INSTRUCCIONES Y VÍAS DE PAGO (TRANSFERENCIA BANCARIA)</b>", style_section_title)
        ],
        [
            Paragraph(
                "• <b>Banco:</b> Banco Santander Río &nbsp;&nbsp;|&nbsp;&nbsp; "
                "• <b>Tipo de Cuenta:</b> Cuenta Corriente en Pesos<br/>"
                "• <b>Titular:</b> Centro Educativo Transformar para educar S.R.L. &nbsp;&nbsp;|&nbsp;&nbsp; "
                "• <b>CUIT:</b> 30-71234567-8<br/>"
                "• <b>CBU:</b> 0720123456789012345678 &nbsp;&nbsp;|&nbsp;&nbsp; "
                "• <b>Alias:</b> <b>EDUCAR.TRANSFORMAR.PAGO</b><br/><br/>"
                "<i>Una vez realizada la transferencia, adjunte el comprobante desde la <b>App Móvil</b> "
                "en la sección de Pagos o mediante el portal web para su inmediata acreditación.</i>",
                style_cell,
            )
        ],
    ]
    pago_table = Table(pago_box_data, colWidths=[540])
    pago_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#3B82F6")),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(pago_table)
    story.append(Spacer(1, 16))

    # 5. Pie institucional
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94A3B8"), spaceBefore=0, spaceAfter=8))
    story.append(
        Paragraph(
            "Centro Educativo «Transformar para educar» — Documento no válido como factura fiscal AFIP — "
            "Liquidación interna de aranceles educativos.",
            style_footer,
        )
    )

    doc.build(story)
    return buffer.getvalue()
