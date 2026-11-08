from decimal import Decimal, ROUND_HALF_UP


CENTAVO = Decimal("0.01")


def _decimal(value):
    return Decimal(str(value or "0")).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def construir_conceptos_cuota(alumno, monto_base, nivel=None):
    """Builds an immutable-at-issuance breakdown from the student's active services."""
    curso = getattr(alumno, "id_curso", None)
    nivel_nombre = nivel or (
        curso.nivel_educativo.nombre
        if curso and curso.nivel_educativo_id
        else "Sin nivel"
    )
    conceptos = [{
        "tipo": "cuota_base",
        "concepto": f"Cuota base ({nivel_nombre})",
        "monto": _decimal(monto_base),
        "nivel": nivel_nombre,
    }]

    deportes = [
        inscripcion
        for inscripcion in alumno.inscripciones_deportivas.all()
        if (inscripcion.estado or "").casefold() == "activa"
        and (inscripcion.id_grupo.estado or "").casefold() == "activo"
    ][:2]
    for inscripcion in deportes:
        grupo = inscripcion.id_grupo
        disciplina = grupo.id_disciplina
        docente = grupo.profesor_responsable
        persona_docente = docente.id_persona if docente else None
        docente_nombre = (
            f"{persona_docente.nombre} {persona_docente.apellido}".strip()
            if persona_docente
            else ""
        )
        horario = (
            f"{grupo.dia_semana} {grupo.hora_inicio.strftime('%H:%M')}-"
            f"{grupo.hora_fin.strftime('%H:%M')}"
        )
        conceptos.append({
            "tipo": "deporte",
            "concepto": f"Deporte: {disciplina.nombre}",
            "monto": _decimal(disciplina.monto_mensual),
            "deporte_id": disciplina.id_disciplina,
            "deporte": disciplina.nombre,
            "nivel": grupo.nivel_educativo.nombre,
            "horario": horario,
            "docente_id": docente.legajo if docente else None,
            "docente": docente_nombre,
        })

    transporte = next((
        inscripcion
        for inscripcion in alumno.inscripciones_transporte.all()
        if (inscripcion.estado or "").casefold() == "activa"
        and (inscripcion.id_recorrido.estado or "").casefold() == "activo"
    ), None)
    if transporte:
        recorrido = transporte.id_recorrido
        conceptos.append({
            "tipo": "transporte",
            "concepto": f"Transporte: {recorrido.nombre}",
            "monto": _decimal(recorrido.monto_mensual),
            "nivel": nivel_nombre,
            "recorrido_id": recorrido.id_recorrido,
            "recorrido": recorrido.nombre,
        })

    comedor = next((
        inscripcion
        for inscripcion in alumno.inscripciones_comedor.all()
        if (inscripcion.estado or "").casefold() == "activa"
        and (inscripcion.id_servicio.estado or "").casefold() == "activo"
    ), None)
    if comedor:
        servicio = comedor.id_servicio
        conceptos.append({
            "tipo": "comedor",
            "concepto": f"Comedor: {servicio.nombre}",
            "monto": _decimal(servicio.monto_mensual),
            "nivel": nivel_nombre,
        })

    return conceptos


def serializar_conceptos_cuota(conceptos):
    """Convert Decimal values to JSON-safe strings while retaining category metadata."""
    return [
        {**concepto, "monto": format(_decimal(concepto.get("monto")), ".2f")}
        for concepto in conceptos
    ]


def distribuir_pago_por_conceptos(cuota):
    """Allocate approved payments proportionally; return None for missing/inconsistent snapshots."""
    conceptos = cuota.conceptos
    if not isinstance(conceptos, list) or not conceptos:
        return None

    montos = [_decimal(item.get("monto")) for item in conceptos if isinstance(item, dict)]
    if len(montos) != len(conceptos):
        return None
    total_conceptos = sum(montos, Decimal("0.00"))
    total_cuota = _decimal(cuota.total_obligacion)
    if total_conceptos <= 0 or total_conceptos != total_cuota:
        return None

    total_pagado = min(_decimal(cuota.monto_pagado_actual()), total_conceptos)
    asignados = []
    restante = total_pagado
    for indice, (concepto, monto) in enumerate(zip(conceptos, montos)):
        if indice == len(conceptos) - 1:
            importe = restante
        else:
            importe = (total_pagado * monto / total_conceptos).quantize(
                CENTAVO,
                rounding=ROUND_HALF_UP,
            )
            importe = min(importe, restante)
        restante -= importe
        asignados.append((concepto, importe))
    return asignados


def agrupar_reporte_financiero(cuotas):
    """Summarize billed and paid amounts from saved concept snapshots only."""
    dimensiones = {
        "deportes": {},
        "niveles": {},
        "horarios": {},
        "docentes": {},
        "recorridos": {},
    }
    total_sin_desglose_facturado = Decimal("0.00")
    total_sin_desglose_pagado = Decimal("0.00")
    cuotas_sin_desglose = 0

    def acumular(dimension, nombre, facturado, pagado):
        if not nombre:
            return
        fila = dimensiones[dimension].setdefault(
            str(nombre),
            {"nombre": str(nombre), "facturado": Decimal("0.00"), "pagado": Decimal("0.00")},
        )
        fila["facturado"] += facturado
        fila["pagado"] += pagado

    for cuota in cuotas:
        asignados = distribuir_pago_por_conceptos(cuota)
        if asignados is None:
            cuotas_sin_desglose += 1
            total_sin_desglose_facturado += _decimal(cuota.total_obligacion)
            total_sin_desglose_pagado += _decimal(cuota.monto_pagado_actual())
            continue

        for concepto, pago_asignado in asignados:
            tipo = concepto.get("tipo")
            facturado = _decimal(concepto.get("monto"))
            nivel = concepto.get("nivel")
            if nivel:
                acumular("niveles", nivel, facturado, pago_asignado)
            if tipo == "deporte":
                acumular("deportes", concepto.get("deporte"), facturado, pago_asignado)
                acumular("horarios", concepto.get("horario"), facturado, pago_asignado)
                acumular("docentes", concepto.get("docente"), facturado, pago_asignado)
            elif tipo == "transporte":
                acumular("recorridos", concepto.get("recorrido"), facturado, pago_asignado)

    resultado = {
        "cuotas_sin_desglose": cuotas_sin_desglose,
        "facturado_sin_desglose": format(total_sin_desglose_facturado, ".2f"),
        "pagado_sin_desglose": format(total_sin_desglose_pagado, ".2f"),
    }
    for dimension, filas in dimensiones.items():
        resultado[dimension] = [
            {
                "nombre": fila["nombre"],
                "facturado": format(fila["facturado"], ".2f"),
                "pagado": format(fila["pagado"], ".2f"),
            }
            for fila in sorted(filas.values(), key=lambda item: item["nombre"].casefold())
        ]
    return resultado

