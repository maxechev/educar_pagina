"""
Reorganiza los horarios académicos existentes.

Uso recomendado desde la carpeta del proyecto:

    python manage.py shell < reorganizar_horarios.py

El script funciona en modo simulación por defecto. Para aplicar los cambios,
cambiar SIMULACION a False. No modifica grupos deportivos, alumnos, cursos,
materias ni migraciones.
"""

import json
import os
from datetime import time

import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "educar_pagina_proyecto.settings")
django.setup()

from django.db import transaction  # noqa: E402
from django.db.models import Count  # noqa: E402
from django.utils import timezone  # noqa: E402

from core.models import Curso, CursoCursaMaterias, GrupoDeportivo, Horario  # noqa: E402


# Dejar en True para revisar primero el informe sin guardar cambios.
SIMULACION = False

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes"]
BLOQUES_MANANA = [
    ("07:30", "08:50"),
    ("09:00", "10:20"),
    ("10:30", "11:50"),
    ("12:00", "13:20"),
]
BLOQUES_TARDE = [
    ("13:30", "14:50"),
    ("15:00", "16:20"),
    ("16:30", "17:50"),
    ("18:00", "19:20"),
]


def parse_time(value):
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def slots_para_turno(turno):
    bloques = BLOQUES_MANANA if (turno or "").strip().lower() == "mañana" else BLOQUES_TARDE
    return [
        (dia, parse_time(inicio), parse_time(fin))
        for dia in DIAS
        for inicio, fin in bloques
    ]


def asignar_slots(ccms, slots, stats):
    """Asigna los bloques según ``Materia.cantidad_clases``.

    De esta manera el script respeta la cantidad configurada para cada
    materia, en lugar de imponer la misma cantidad a todas.
    """
    clases_por_ccm = {
        ccm: max(1, int(ccm.id_materia.cantidad_clases or 1))
        for ccm in ccms
    }
    necesarios = sum(clases_por_ccm.values())
    if necesarios > len(slots):
        # Prioridad elegida: una clase semanal por materia para que todos los
        # cursos tengan horarios sin superposiciones.
        clases_por_ccm = {ccm: 1 for ccm in ccms}
        necesarios = len(ccms)
        stats["cursos_con_una_clase"] += 1
    if necesarios > len(slots):
        stats["cursos_sin_slots"] += 1
        return {ccm: [] for ccm in ccms}

    resultado = {}
    posicion = 0
    for ccm in ccms:
        cantidad = clases_por_ccm[ccm]
        resultado[ccm] = slots[posicion:posicion + cantidad]
        posicion += cantidad
    return resultado


def formato_legacy(asignaciones):
    """Construye el JSON antiguo sin perder los horarios normalizados.

    El modelo Horario sigue siendo la fuente principal. Si hay dos horarios
    en el mismo día, el respaldo contiene una lista para no sobrescribirlos.
    """
    por_dia = {}
    for dia, inicio, fin in asignaciones:
        valor = f"{inicio.strftime('%H:%M')}-{fin.strftime('%H:%M')}"
        por_dia.setdefault(dia, []).append(valor)
    resultado = {
        dia: valores[0] if len(valores) == 1 else valores
        for dia, valores in por_dia.items()
    }
    return json.dumps(resultado, ensure_ascii=False)


def backup_datos():
    """Guarda una copia legible antes de aplicar una ejecución real."""
    marca = timezone.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(os.path.dirname(__file__), f"backup_horarios_{marca}.json")
    datos = {
        "generado": timezone.now().isoformat(),
        "horarios": [
            {
                "id_horario": horario.id_horario,
                "curso_materia_id": horario.curso_materia_id,
                "grupo_deportivo_id": horario.grupo_deportivo_id,
                "dia_semana": horario.dia_semana,
                "hora_inicio": horario.hora_inicio.isoformat(),
                "hora_fin": horario.hora_fin.isoformat(),
            }
            for horario in Horario.objects.all().order_by("id_horario")
        ],
        "curso_cursa_materias": [
            {
                "id": ccm.id,
                "id_curso": ccm.id_curso_id,
                "id_materia": ccm.id_materia_id,
                "horarios": ccm.horarios,
            }
            for ccm in CursoCursaMaterias.objects.all().order_by("id")
        ],
        "grupos_deportivos": [
            {
                "id_grupo": grupo.id_grupo,
                "dia_semana": grupo.dia_semana,
                "turno": grupo.turno,
                "hora_inicio": grupo.hora_inicio.isoformat(),
                "hora_fin": grupo.hora_fin.isoformat(),
            }
            for grupo in GrupoDeportivo.objects.all().order_by("id_grupo")
        ],
    }
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)
    return ruta


def duplicados_academicos():
    return Horario.objects.filter(
        curso_materia__isnull=False,
        grupo_deportivo__isnull=True,
    ).values(
        "curso_materia_id", "dia_semana", "hora_inicio", "hora_fin"
    ).annotate(cantidad=Count("id_horario")).filter(cantidad__gt=1).count()


def separar_relaciones_duplicadas(ccms, stats):
    """Conserva una relación por materia para asignar un único horario."""
    unicas = []
    vistas = set()
    duplicadas = []
    for ccm in ccms:
        if ccm.id_materia_id in vistas:
            duplicadas.append(ccm)
        else:
            vistas.add(ccm.id_materia_id)
            unicas.append(ccm)
    stats["relaciones_duplicadas"] += len(duplicadas)
    stats["relaciones_a_eliminar"] += len(duplicadas)
    return unicas, duplicadas


def procesar_curso(curso, stats, simulacion):
    ccms_todas = list(
        CursoCursaMaterias.objects.filter(id_curso=curso)
        .select_related("id_materia")
        .order_by("id_materia__nombre", "id")
    )
    if not ccms_todas:
        stats["cursos_sin_materias"] += 1
        return

    ccms, relaciones_duplicadas = separar_relaciones_duplicadas(ccms_todas, stats)

    asignaciones = asignar_slots(ccms, slots_para_turno(curso.turno), stats)
    if any(not slots for slots in asignaciones.values()):
        print(f"  ⚠️ {curso.id_curso}: no hay slots suficientes; no se modifica.")
        return

    existentes = Horario.objects.filter(
        curso_materia__id_curso=curso,
        grupo_deportivo__isnull=True,
    )
    stats["eliminados"] += existentes.count()
    stats["creados"] += sum(len(slots) for slots in asignaciones.values())

    if simulacion:
        return

    existentes.delete()
    for duplicada in relaciones_duplicadas:
        duplicada.delete()
    for ccm, slots in asignaciones.items():
        for dia, inicio, fin in slots:
            Horario.objects.create(
                curso_materia=ccm,
                grupo_deportivo=None,
                dia_semana=dia,
                hora_inicio=inicio,
                hora_fin=fin,
            )
        ccm.horarios = formato_legacy(slots)
        ccm.save(update_fields=["horarios"])
    stats["sincronizados"] += len(ccms)


def main():
    stats = {
        "cursos_procesados": 0,
        "creados": 0,
        "eliminados": 0,
        "sincronizados": 0,
        "cursos_sin_materias": 0,
        "cursos_sin_slots": 0,
        "cursos_con_una_clase": 0,
        "relaciones_duplicadas": 0,
        "relaciones_a_eliminar": 0,
    }

    print("=" * 70)
    print("REORGANIZACIÓN DE HORARIOS ACADÉMICOS")
    print(f"Modo: {'SIMULACIÓN' if SIMULACION else 'EJECUCIÓN'}")
    print(f"Duplicados actuales en Horario: {duplicados_academicos()}")
    print("=" * 70)

    if not SIMULACION:
        ruta_backup = backup_datos()
        print(f"Copia de seguridad creada en: {ruta_backup}")

    cursos = Curso.objects.select_related("nivel_educativo").order_by(
        "nivel_educativo__nombre", "anio", "comision", "turno"
    )
    for curso in cursos:
        print(
            f"Procesando {curso.nivel_educativo.nombre} {curso.anio}° "
            f"{curso.comision} ({curso.turno})"
        )
        procesar_curso(curso, stats, SIMULACION)
        stats["cursos_procesados"] += 1

    print("\nINFORME")
    for clave, valor in stats.items():
        print(f"{clave}: {valor}")
    if SIMULACION:
        print("\nNo se guardaron cambios. Cambiá SIMULACION = False para aplicar.")
    else:
        print("\nCambios aplicados correctamente.")


if __name__ == "__main__":
    with transaction.atomic():
        main()
