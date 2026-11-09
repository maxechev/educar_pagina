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
        "clave": "cuota_base",
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
            "clave": f"deporte:{disciplina.id_disciplina}",
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
            "clave": f"transporte:{recorrido.id_recorrido}",
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
            "clave": f"comedor:{servicio.id_servicio}",
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


def clave_concepto(concepto):
    """Return a stable key for both current snapshots and older snapshots."""
    clave = concepto.get("clave")
    if clave:
        return str(clave)
    tipo = str(concepto.get("tipo") or "").strip()
    if tipo == "cuota_base":
        return "cuota_base"
    campos_id = {
        "deporte": "deporte_id",
        "transporte": "recorrido_id",
        "comedor": "servicio_id",
    }
    identificador = concepto.get(campos_id.get(tipo, ""))
    if identificador is not None:
        return f"{tipo}:{identificador}"
    nombre = str(concepto.get("concepto") or tipo or "concepto").strip().casefold()
    return f"{tipo}:{nombre}"


def _repartir_importe_proporcional(importe, conceptos):
    """Allocate a legacy payment over concepts without inventing new categories."""
    montos = [_decimal(item.get("monto")) for item in conceptos]
    total = sum(montos, Decimal("0.00"))
    if total <= 0:
        return [Decimal("0.00") for _ in conceptos]
    restante = min(_decimal(importe), total)
    asignados = []
    for indice, monto in enumerate(montos):
        if indice == len(montos) - 1:
            parte = restante
        else:
            parte = (_decimal(importe) * monto / total).quantize(
                CENTAVO,
                rounding=ROUND_HALF_UP,
            )
            parte = min(parte, restante, monto)
        asignados.append(parte)
        restante -= parte
    return asignados


def disponibilidad_conceptos_pago(cuota):
    """Return the remaining payable amount for each issued concept snapshot.

    Legacy payments without a saved allocation keep the historical proportional
    distribution. Legacy payments awaiting review block the whole fee because
    their intended concepts are unknown.
    """
    conceptos = cuota.conceptos
    if not isinstance(conceptos, list) or not conceptos:
        return []
    if any(not isinstance(item, dict) for item in conceptos):
        return []

    total_conceptos = sum((_decimal(item.get("monto")) for item in conceptos), Decimal("0.00"))
    if total_conceptos != _decimal(cuota.total_obligacion):
        return []

    claves = [clave_concepto(item) for item in conceptos]
    if len(set(claves)) != len(claves):
        return []
    pagado_por_clave = {clave: Decimal("0.00") for clave in claves}
    en_revision_por_clave = {clave: Decimal("0.00") for clave in claves}
    pago_legacy_aprobado = Decimal("0.00")
    pago_legacy_en_revision = False

    for pago in cuota.pagos.all():
        asignacion = pago.conceptos_aplicados or {}
        tiene_asignacion = isinstance(asignacion, dict) and bool(asignacion)
        if pago.estado == "Pagado":
            if tiene_asignacion:
                for clave, importe in asignacion.items():
                    if clave in pagado_por_clave:
                        pagado_por_clave[clave] += _decimal(importe)
            else:
                pago_legacy_aprobado += _decimal(pago.importe)
        elif pago.estado in {"Pendiente", "En revisión"}:
            if tiene_asignacion:
                for clave, importe in asignacion.items():
                    if clave in en_revision_por_clave:
                        en_revision_por_clave[clave] += _decimal(importe)
            else:
                pago_legacy_en_revision = True

    if pago_legacy_aprobado:
        reparto_legacy = _repartir_importe_proporcional(pago_legacy_aprobado, conceptos)
        for clave, importe in zip(claves, reparto_legacy):
            pagado_por_clave[clave] += importe

    disponibilidad = []
    for concepto, clave in zip(conceptos, claves):
        monto = _decimal(concepto.get("monto"))
        pagado = min(pagado_por_clave[clave], monto)
        en_revision = min(en_revision_por_clave[clave], max(monto - pagado, Decimal("0.00")))
        saldo_disponible = max(monto - pagado - en_revision, Decimal("0.00"))
        if pago_legacy_en_revision:
            saldo_disponible = Decimal("0.00")
        disponibilidad.append({
            **concepto,
            "clave": clave,
            "monto": format(monto, ".2f"),
            "monto_pagado": format(pagado, ".2f"),
            "monto_en_revision": format(en_revision, ".2f"),
            "saldo_disponible": format(saldo_disponible, ".2f"),
            "bloqueado_por_revision": pago_legacy_en_revision,
        })
    return disponibilidad


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

    pagos_prefetch = getattr(cuota, "_prefetched_objects_cache", {}).get("pagos")
    if pagos_prefetch is None:
        pagos = list(cuota.pagos.filter(estado="Pagado"))
    else:
        pagos = [pago for pago in pagos_prefetch if pago.estado == "Pagado"]
    pagado_por_clave = {clave_concepto(concepto): Decimal("0.00") for concepto in conceptos}
    pagos_legacy = Decimal("0.00")
    for pago in pagos:
        asignacion = pago.conceptos_aplicados or {}
        if isinstance(asignacion, dict) and asignacion:
            for clave, importe in asignacion.items():
                if clave not in pagado_por_clave:
                    return None
                pagado_por_clave[clave] += _decimal(importe)
        else:
            pagos_legacy += _decimal(pago.importe)

    if pagos_legacy:
        reparto_legacy = _repartir_importe_proporcional(pagos_legacy, conceptos)
        for concepto, importe in zip(conceptos, reparto_legacy):
            pagado_por_clave[clave_concepto(concepto)] += importe

    return [
        (concepto, min(pagado_por_clave[clave_concepto(concepto)], _decimal(concepto.get("monto"))))
        for concepto in conceptos
    ]


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

