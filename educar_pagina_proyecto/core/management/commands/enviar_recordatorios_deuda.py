from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.factura_pdf import formatear_moneda
from core.models import Cuota, Tutor


class Command(BaseCommand):
    help = (
        "Envía automáticamente recordatorios de deuda por correo a los padres/tutores "
        "con saldo pendiente el día 20 de cada mes, excluyendo comprobantes en revisión (HU_M07)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--periodo",
            type=str,
            default=None,
            help="Filtrar por período específico (ej. 'Noviembre 2026' o '2026-11'). Por defecto analiza cuotas vigentes.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula la búsqueda y el envío sin despachar correos electrónicos reales.",
        )

    def handle(self, *args, **options):
        periodo_filtro = options["periodo"]
        dry_run = options["dry_run"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"=== Recordatorio Automático de Deuda (Día 20) "
                f"({'MODO SIMULACIÓN / DRY-RUN' if dry_run else 'PRODUCCIÓN'}) ==="
            )
        )

        cuotas_qs = (
            Cuota.objects.select_related(
                "id_tutor__id_persona__id_usuario",
                "id_legajo_alumno__id_persona",
                "id_legajo_alumno__id_curso__nivel_educativo",
            )
            .prefetch_related(
                "pagos",
                "comprobantes__pago",
            )
            .all()
        )

        if periodo_filtro:
            cuotas_qs = cuotas_qs.filter(periodo__icontains=periodo_filtro.strip())

        # Agrupación por tutor
        deudas_por_tutor = defaultdict(list)
        total_cuotas_evaluadas = 0
        total_excluidas_en_revision = 0
        total_al_dia = 0

        for cuota in cuotas_qs:
            total_cuotas_evaluadas += 1
            total_obligacion = cuota.total_obligacion or Decimal("0")
            pagado = cuota.monto_pagado_actual()
            saldo = max(total_obligacion - pagado, Decimal("0"))

            if saldo <= Decimal("0"):
                total_al_dia += 1
                continue

            # Evaluar comprobantes en revisión
            importe_en_revision = Decimal("0")
            for comp in cuota.comprobantes.all():
                if comp.pago and (comp.pago.estado or "").casefold() == "en revisión":
                    importe_en_revision += (comp.pago.importe or Decimal("0"))
                elif (comp.estado or "").casefold() == "en revisión":
                    # Si el comprobante no tiene pago vinculado directo pero está en revisión
                    importe_en_revision += saldo

            if importe_en_revision >= saldo:
                total_excluidas_en_revision += 1
                continue

            # El tutor mantiene saldo pendiente neto
            saldo_neto = saldo - importe_en_revision
            deudas_por_tutor[cuota.id_tutor].append({
                "cuota": cuota,
                "alumno": cuota.id_legajo_alumno,
                "saldo": saldo_neto,
                "periodo": cuota.periodo,
                "vencimiento": cuota.fecha_vencimiento,
            })

        self.stdout.write(
            f"[*] Cuotas evaluadas: {total_cuotas_evaluadas}\n"
            f"[*] Cuotas con comprobante en revisión (excluidas): {total_excluidas_en_revision}\n"
            f"[*] Cuotas al día / pagadas: {total_al_dia}\n"
            f"[*] Tutores con deuda activa: {len(deudas_por_tutor)}\n"
        )

        correos_enviados = 0
        monto_total_deuda = Decimal("0")

        for tutor, items in deudas_por_tutor.items():
            persona_tutor = tutor.id_persona
            nombre_tutor = f"{persona_tutor.nombre} {persona_tutor.apellido}".strip() if persona_tutor else "Tutor"
            email_tutor = None
            if persona_tutor and getattr(persona_tutor, "id_usuario", None) and persona_tutor.id_usuario.correo:
                email_tutor = persona_tutor.id_usuario.correo
            elif getattr(tutor, "email_contacto", None):
                email_tutor = tutor.email_contacto

            total_tutor = sum((it["saldo"] for it in items), Decimal("0"))
            monto_total_deuda += total_tutor

            # Construir detalle de cuotas para el cuerpo del mensaje
            lineas_detalle = []
            for it in items:
                alumno = it["alumno"]
                persona_alumno = alumno.id_persona
                nom_al = f"{persona_alumno.nombre} {persona_alumno.apellido}".strip()
                vto_str = it["vencimiento"].strftime("%d/%m/%Y") if it["vencimiento"] else "Vencido"
                lineas_detalle.append(
                    f"  • {nom_al} (Legajo {alumno.legajo}) - {it['periodo']}: "
                    f"Saldo: {formatear_moneda(it['saldo'])} (Vencimiento: {vto_str})"
                )

            detalle_texto = "\n".join(lineas_detalle)

            cuerpo_email = (
                f"Estimado/a {nombre_tutor}:\n\n"
                f"Nos comunicamos desde la Administración del Centro Educativo «Transformar para educar» "
                f"para recordarle que, de acuerdo con nuestro registro administrativo al día 20 del mes en curso, "
                f"registra un saldo pendiente de regularización correspondiente a los siguientes aranceles:\n\n"
                f"{detalle_texto}\n\n"
                f"--------------------------------------------------\n"
                f"TOTAL SALDO PENDIENTE: {formatear_moneda(total_tutor)}\n"
                f"--------------------------------------------------\n\n"
                f"Para regularizar la situación, puede transferir a los siguientes datos bancarios:\n"
                f"• Banco: Banco Santander Río\n"
                f"• Titular: Centro Educativo Transformar para educar S.R.L.\n"
                f"• CUIT: 30-71234567-8\n"
                f"• CBU: 0720123456789012345678\n"
                f"• Alias: EDUCAR.TRANSFORMAR.PAGO\n\n"
                f"Una vez realizada la transferencia bancaria, le solicitamos adjuntar el comprobante "
                f"directamente desde la Aplicación Móvil en la sección 'Cuotas' para su inmediata imputación.\n\n"
                f"Si usted ya realizó el pago en las últimas 24 a 48 horas y su comprobante se encuentra en revisión, "
                f"por favor desestime el presente aviso.\n\n"
                f"Atentamente,\n"
                f"Departamento de Cobranzas y Aranceles\n"
                f"Centro Educativo «Transformar para educar»"
            )

            if dry_run:
                self.stdout.write(
                    f"[SIMULADO] Recordatorio a {nombre_tutor} ({email_tutor or 'Sin email'}): "
                    f"{len(items)} cuota(s) pendiente(s) por {formatear_moneda(total_tutor)}"
                )
                correos_enviados += 1
                continue

            if not email_tutor:
                self.stdout.write(
                    self.style.WARNING(
                        f"[-] Omitido envío a {nombre_tutor} (Tutor #{tutor.id}): No tiene correo electrónico registrado."
                    )
                )
                continue

            try:
                email_msg = EmailMessage(
                    subject="Recordatorio de Regularización de Cuota Escolar - Centro Educativo Transformar para educar",
                    body=cuerpo_email,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "educarparatransformarcolegio@gmail.com"),
                    to=[email_tutor],
                )
                email_msg.send(fail_silently=True)
                correos_enviados += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[+] Recordatorio enviado a {nombre_tutor} <{email_tutor}>: "
                        f"{len(items)} cuota(s), total {formatear_moneda(total_tutor)}"
                    )
                )
            except Exception as ex:
                self.stdout.write(
                    self.style.ERROR(f"[-] Error enviando recordatorio a {email_tutor}: {ex}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n=== Resumen de Recordatorios (Día 20) ===\n"
                f"• Tutores morosos identificados: {len(deudas_por_tutor)}\n"
                f"• Recordatorios enviados: {correos_enviados}\n"
                f"• Total saldo pendiente notificado: {formatear_moneda(monto_total_deuda)}\n"
            )
        )
