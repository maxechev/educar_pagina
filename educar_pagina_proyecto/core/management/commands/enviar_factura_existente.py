from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.factura_pdf import generar_factura_pdf
from core.models import Cuota, TutorTutoraAlumno


class Command(BaseCommand):
    help = (
        "Genera en memoria y envía una copia PDF de una cuota existente a un destinatario explícito. "
        "No modifica la cuota ni guarda archivos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--cuota-id", type=int, required=True)
        parser.add_argument("--legajo", type=int, required=True)
        parser.add_argument("--destinatario", required=True)

    def handle(self, *args, **options):
        try:
            cuota = Cuota.objects.select_related(
                "id_legajo_alumno__id_persona",
                "id_legajo_alumno__id_curso__nivel_educativo",
                "id_tutor__id_persona__id_usuario",
            ).get(
                id_cuota=options["cuota_id"],
                id_legajo_alumno__legajo=options["legajo"],
            )
        except Cuota.DoesNotExist as exc:
            raise CommandError("No existe esa cuota para el legajo indicado; no se envió ningún correo.") from exc

        alumno = cuota.id_legajo_alumno
        tutor = cuota.id_tutor
        if not TutorTutoraAlumno.objects.filter(id_tutor=tutor, id_alumno=alumno).exists():
            raise CommandError("El tutor de la cuota no está asociado al alumno; no se envió ningún correo.")

        destinatario = options["destinatario"].strip()
        if not destinatario or "@" not in destinatario:
            raise CommandError("Debe indicar un correo destinatario válido.")

        total = Decimal(str(cuota.total_obligacion or cuota.monto or "0"))
        base = Decimal(str(cuota.monto or "0"))
        conceptos = [{"concepto": "Cuota base", "monto": base}]
        otros = total - base
        if otros > 0:
            conceptos.append({"concepto": "Otros conceptos incluidos en el total registrado", "monto": otros})

        hoy = timezone.localdate()
        num_factura = f"FAC-{cuota.periodo[:3].upper()}-{cuota.id_cuota:05d}"
        pdf_bytes = generar_factura_pdf(
            cuota=cuota,
            alumno=alumno,
            tutor=tutor,
            desglose_conceptos=conceptos,
            numero_factura=num_factura,
            fecha_emision=hoy.strftime("%d/%m/%Y"),
        )
        nombre_alumno = f"{alumno.id_persona.nombre} {alumno.id_persona.apellido}".strip()
        email = EmailMessage(
            subject=f"Copia de prueba de liquidación {cuota.periodo} - {nombre_alumno}",
            body=(
                "Se adjunta una copia de prueba de la liquidación existente. "
                "No se modificó la cuota ni se creó una obligación nueva."
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[destinatario],
        )
        email.attach(f"factura_{cuota.id_cuota}.pdf", pdf_bytes, "application/pdf")
        enviados = email.send(fail_silently=False)
        self.stdout.write(self.style.SUCCESS(
            f"Copia PDF de cuota #{cuota.id_cuota} ({nombre_alumno}, {cuota.periodo}) "
            f"enviada a {destinatario}. No se modificó la cuota. Mensajes enviados: {enviados}."
        ))
