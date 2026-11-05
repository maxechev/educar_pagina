from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.factura_pdf import formatear_moneda, generar_factura_pdf
from core.models import (
    Alumno,
    Arancel,
    Cuota,
    InscripcionComedor,
    InscripcionDeportiva,
    InscripcionTransporte,
    Tutor,
    TutorTutoraAlumno,
)

MESES_PERIODO = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
)

NIVELES_EQUIVALENTES = {
    "inicial": "inicial",
    "primaria": "primario",
    "primario": "primario",
    "secundaria": "secundario",
    "secundario": "secundario",
}


def _normalizar_nivel(nombre):
    limpio = " ".join((nombre or "").strip().casefold().split())
    return NIVELES_EQUIVALENTES.get(limpio, limpio)


class Command(BaseCommand):
    help = (
        "Calcula y emite las facturas/cuotas mensuales en PDF con discriminación "
        "de conceptos (cuota base, deportes, transporte, comedor) y las envía por correo al tutor (HU_M06)."
    )

    def add_arguments(self, parser):
        hoy = timezone.localdate()
        parser.add_argument(
            "--mes",
            type=int,
            default=hoy.month,
            help="Mes a facturar (1-12). Por defecto mes actual.",
        )
        parser.add_argument(
            "--anio",
            type=int,
            default=hoy.year,
            help="Año a facturar (YYYY). Por defecto año actual.",
        )
        parser.add_argument(
            "--vencimiento",
            type=str,
            default=None,
            help="Fecha de vencimiento (YYYY-MM-DD). Por defecto día 10 del mes facturado.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula la emisión sin guardar en base de datos ni enviar correos.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenera cuotas y reenvía correos incluso si la cuota ya existía.",
        )

    def handle(self, *args, **options):
        mes = options["mes"]
        anio = options["anio"]
        dry_run = options["dry_run"]
        force = options["force"]

        if not (1 <= mes <= 12):
            self.stderr.write(self.style.ERROR(f"Mes inválido: {mes}. Debe estar entre 1 y 12."))
            return

        periodo_nombre = f"{MESES_PERIODO[mes - 1]} {anio}"

        # Resolver fecha de vencimiento
        if options["vencimiento"]:
            try:
                fecha_vencimiento = date.fromisoformat(options["vencimiento"])
            except ValueError:
                self.stderr.write(self.style.ERROR("Formato de fecha de vencimiento inválido. Use YYYY-MM-DD."))
                return
        else:
            fecha_vencimiento = date(anio, mes, 10)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"=== Emisión de Facturas Mensuales: {periodo_nombre} "
                f"({'MODO SIMULACIÓN / DRY-RUN' if dry_run else 'PRODUCCIÓN'}) ==="
            )
        )

        # Mapa de aranceles base
        aranceles_por_nivel = {}
        for arancel in Arancel.objects.all().order_by("id_arancel"):
            clave = _normalizar_nivel(arancel.nivel)
            aranceles_por_nivel.setdefault(clave, []).append(arancel.monto)

        alumnos = (
            Alumno.objects.filter(estado="Activo")
            .select_related("id_persona", "id_curso__nivel_educativo")
            .prefetch_related(
                "inscripciones_deportivas__id_grupo__id_disciplina",
                "inscripciones_transporte__id_recorrido",
                "inscripciones_comedor__id_servicio",
            )
            .order_by("id_persona__apellido", "id_persona__nombre")
        )

        if not alumnos.exists():
            # Si no hay con estado 'Activo', buscar todos los alumnos registrados
            alumnos = (
                Alumno.objects.all()
                .select_related("id_persona", "id_curso__nivel_educativo")
                .prefetch_related(
                    "inscripciones_deportivas__id_grupo__id_disciplina",
                    "inscripciones_transporte__id_recorrido",
                    "inscripciones_comedor__id_servicio",
                )
                .order_by("id_persona__apellido", "id_persona__nombre")
            )

        emitidas_count = 0
        omitidas_count = 0
        emails_enviados = 0
        total_facturado = Decimal("0")

        for alumno in alumnos:
            persona_alumno = alumno.id_persona
            nombre_alumno = f"{persona_alumno.nombre} {persona_alumno.apellido}".strip()

            # Resolver tutor asociado
            relacion = TutorTutoraAlumno.objects.filter(id_alumno=alumno).select_related(
                "id_tutor__id_persona__id_usuario"
            ).first()

            if not relacion or not relacion.id_tutor:
                self.stdout.write(
                    self.style.WARNING(f"[-] Omitido {nombre_alumno} (Legajo {alumno.legajo}): Sin tutor asignado.")
                )
                omitidas_count += 1
                continue

            tutor = relacion.id_tutor

            # Cuota base según nivel
            nivel_nombre = alumno.id_curso.nivel_educativo.nombre if (alumno.id_curso and alumno.id_curso.nivel_educativo) else "General"
            clave_nivel = _normalizar_nivel(nivel_nombre)
            aranceles_candidatos = aranceles_por_nivel.get(clave_nivel, [])
            monto_base = aranceles_candidatos[0] if aranceles_candidatos else Decimal("30000.00")

            desglose = [
                {
                    "concepto": f"Cuota Base de Enseñanza ({nivel_nombre})",
                    "monto": monto_base,
                }
            ]

            # Servicios: Deportes (máx 2)
            deportes_activas = [
                i for i in alumno.inscripciones_deportivas.all()
                if (i.estado or "").casefold() == "activa"
                and (i.id_grupo.estado or "").casefold() == "activo"
            ][:2]
            for dep in deportes_activas:
                monto_dep = dep.id_grupo.id_disciplina.monto_mensual or Decimal("0")
                desglose.append({
                    "concepto": f"Deporte: {dep.id_grupo.id_disciplina.nombre}",
                    "monto": monto_dep,
                })

            # Servicios: Transporte
            transporte_activo = next(
                (
                    i for i in alumno.inscripciones_transporte.all()
                    if (i.estado or "").casefold() == "activa"
                    and (i.id_recorrido.estado or "").casefold() == "activo"
                ),
                None,
            )
            if transporte_activo:
                monto_transp = transporte_activo.id_recorrido.monto_mensual or Decimal("0")
                desglose.append({
                    "concepto": f"Transporte: {transporte_activo.id_recorrido.nombre}",
                    "monto": monto_transp,
                })

            # Servicios: Comedor
            comedor_activo = next(
                (
                    i for i in alumno.inscripciones_comedor.all()
                    if (i.estado or "").casefold() == "activa"
                    and (i.id_servicio.estado or "").casefold() == "activo"
                ),
                None,
            )
            if comedor_activo:
                monto_comedor = comedor_activo.id_servicio.monto_mensual or Decimal("0")
                desglose.append({
                    "concepto": f"Comedor: {comedor_activo.id_servicio.nombre}",
                    "monto": monto_comedor,
                })

            total_alumno = sum((item["monto"] for item in desglose), Decimal("0"))

            # Verificar si ya existe cuota
            cuota_existente = Cuota.objects.filter(
                id_legajo_alumno=alumno,
                periodo=periodo_nombre,
            ).first()

            if cuota_existente and not force:
                self.stdout.write(
                    self.style.NOTICE(
                        f"[*] Ya existe cuota para {nombre_alumno} en {periodo_nombre} (ID {cuota_existente.id_cuota}). "
                        f"Use --force para sobrescribir."
                    )
                )
                continue

            if dry_run:
                self.stdout.write(
                    f"[SIMULADO] Factura para {nombre_alumno}: {formatear_moneda(total_alumno)} "
                    f"({len(desglose)} conceptos)."
                )
                emitidas_count += 1
                total_facturado += total_alumno
                continue

            with transaction.atomic():
                if cuota_existente and force:
                    cuota = cuota_existente
                    cuota.monto = monto_base
                    cuota.monto_total = total_alumno
                    cuota.fecha_vencimiento = fecha_vencimiento
                    cuota.save(update_fields=["monto", "monto_total", "fecha_vencimiento"])
                else:
                    cuota = Cuota.objects.create(
                        periodo=periodo_nombre,
                        monto=monto_base,
                        monto_total=total_alumno,
                        fecha_vencimiento=fecha_vencimiento,
                        estado="Pendiente",
                        id_tutor=tutor,
                        id_legajo_alumno=alumno,
                    )

            # Generar PDF
            num_factura = f"FAC-{anio}{mes:02d}-{cuota.id_cuota:05d}"
            pdf_bytes = generar_factura_pdf(
                cuota=cuota,
                alumno=alumno,
                tutor=tutor,
                desglose_conceptos=desglose,
                numero_factura=num_factura,
                fecha_emision=timezone.localdate().strftime("%d/%m/%Y"),
            )

            # Guardar archivo PDF en media/facturas/YYYY/MM/
            media_dir = Path(settings.MEDIA_ROOT) / "facturas" / str(anio) / f"{mes:02d}"
            media_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = media_dir / f"factura_{cuota.id_cuota}.pdf"
            pdf_path.write_bytes(pdf_bytes)

            # Enviar correo al tutor
            persona_tutor = tutor.id_persona
            email_tutor = None
            if persona_tutor and getattr(persona_tutor, "id_usuario", None) and persona_tutor.id_usuario.correo:
                email_tutor = persona_tutor.id_usuario.correo
            elif getattr(tutor, "email_contacto", None):
                email_tutor = tutor.email_contacto

            if email_tutor:
                try:
                    cuerpo_email = (
                        f"Estimado/a {persona_tutor.nombre} {persona_tutor.apellido}:\n\n"
                        f"Le hacemos llegar la liquidación mensual de aranceles del Centro Educativo "
                        f"«Transformar para educar» correspondiente al período {periodo_nombre} "
                        f"para el alumno/a {nombre_alumno}.\n\n"
                        f"--------------------------------------------------\n"
                        f"Total a abonar: {formatear_moneda(total_alumno)}\n"
                        f"Fecha de vencimiento: {fecha_vencimiento.strftime('%d/%m/%Y')}\n"
                        f"--------------------------------------------------\n\n"
                        f"Datos para Transferencia Bancaria:\n"
                        f"• Banco: Banco Santander Río\n"
                        f"• Titular: Centro Educativo Transformar para educar S.R.L.\n"
                        f"• CUIT: 30-71234567-8\n"
                        f"• CBU: 0720123456789012345678\n"
                        f"• Alias: EDUCAR.TRANSFORMAR.PAGO\n\n"
                        f"Una vez realizada la transferencia bancaria, recuerde ingresar a la aplicación móvil "
                        f"o al sitio web en la sección 'Cuotas' para adjuntar el comprobante correspondiente.\n\n"
                        f"Se adjunta el detalle formal en PDF.\n\n"
                        f"Cordialmente,\n"
                        f"Administración Escolar\n"
                        f"Centro Educativo «Transformar para educar»"
                    )
                    email_msg = EmailMessage(
                        subject=f"Factura de Aranceles {periodo_nombre} - {nombre_alumno}",
                        body=cuerpo_email,
                        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "educarparatransformarcolegio@gmail.com"),
                        to=[email_tutor],
                    )
                    email_msg.attach(
                        f"factura_{cuota.periodo[:3].lower()}_{alumno.legajo}.pdf",
                        pdf_bytes,
                        "application/pdf",
                    )
                    email_msg.send(fail_silently=True)
                    emails_enviados += 1
                except Exception as ex:
                    self.stdout.write(
                        self.style.WARNING(f"[-] Error enviando email a {email_tutor}: {ex}")
                    )

            emitidas_count += 1
            total_facturado += total_alumno
            self.stdout.write(
                self.style.SUCCESS(
                    f"[+] Factura emitida #{num_factura} para {nombre_alumno} ({formatear_moneda(total_alumno)}). "
                    f"Email enviado a {email_tutor or 'Sin email'}."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n=== Resumen de Emisión ===\n"
                f"• Facturas procesadas: {emitidas_count}\n"
                f"• Facturas omitidas: {omitidas_count}\n"
                f"• Correos enviados: {emails_enviados}\n"
                f"• Total facturado: {formatear_moneda(total_facturado)}\n"
            )
        )
