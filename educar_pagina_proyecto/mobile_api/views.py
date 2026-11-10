from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import logging
import os
import secrets
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, send_mail
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.models import (
    Alumno,
    Arancel,
    ComprobantePago,
    Cuota,
    InscripcionComedor,
    InscripcionDeportiva,
    InscripcionTransporte,
    PagoCuota,
    PagoPendiente,
    Persona,
    Tutor,
    TutorTutoraAlumno,
    Usuario,
)
from core.cuota_conceptos import (
    agrupar_reporte_financiero,
    clave_concepto,
    disponibilidad_conceptos_pago,
    distribuir_pago_por_conceptos,
)

from .authentication import MobileTokenAuthentication
from .models import MobilePasswordReset, MobileSession
from .services import mobile_role_for_user
from .tokens import TOKEN_TTL_SECONDS, create_access_token

logger = logging.getLogger(__name__)

MESES_SIMULACION = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)


class IsMobileAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, Usuario)


def _discriminacion_cuota(cuota):
    conceptos = cuota.conceptos
    if not isinstance(conceptos, list) or not conceptos:
        return None
    base = next((item for item in conceptos if item.get("tipo") == "cuota_base"), None)
    deportes = [
        {"nombre": item.get("deporte") or item.get("concepto", "Deporte"), "monto": item.get("monto")}
        for item in conceptos
        if item.get("tipo") == "deporte"
    ]
    transporte = next(
        (
            {"recorrido": item.get("recorrido") or item.get("concepto", "Transporte"), "monto": item.get("monto")}
            for item in conceptos
            if item.get("tipo") == "transporte"
        ),
        None,
    )
    comedor = next(
        ({"monto": item.get("monto")} for item in conceptos if item.get("tipo") == "comedor"),
        None,
    )
    return {
        "cuota_base": base.get("monto") if base else "0.00",
        "deportes": deportes,
        "transporte": transporte,
        "comedor": comedor,
    }


def _conceptos_pago_cuota(cuota, saldo):
    conceptos = disponibilidad_conceptos_pago(cuota)
    if conceptos or saldo <= 0:
        return conceptos
    monto_en_revision = sum(
        (
            pago.importe
            for pago in cuota.pagos.all()
            if pago.estado in {"Pendiente", "En revisión"}
        ),
        Decimal("0.00"),
    )
    monto_en_revision = min(monto_en_revision, saldo)
    disponible = max(saldo - monto_en_revision, Decimal("0.00"))
    return [{
        "clave": "__saldo_total__",
        "tipo": "historico",
        "concepto": "Saldo de la cuota (desglose histórico no disponible)",
        "monto": str(cuota.total_obligacion),
        "monto_pagado": str(cuota.monto_pagado_actual()),
        "monto_en_revision": str(monto_en_revision),
        "saldo_disponible": str(disponible),
        "bloqueado_por_revision": monto_en_revision > 0,
    }]


def user_payload(user, role):
    persona = Persona.objects.filter(id_usuario=user).first()
    name = user.nombre_usuario
    if persona:
        name = f"{persona.nombre} {persona.apellido}".strip()
    return {
        "id": user.pk,
        "username": user.nombre_usuario,
        "name": name,
        "email": user.correo or "",
        "role": role,
    }


class LoginView(APIView):
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mobile_login"
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = str(request.data.get("identifier", "")).strip()
        password = request.data.get("password", "")
        if not identifier or not isinstance(password, str) or not password:
            return Response(
                {"detail": "Ingresá usuario o correo y contraseña."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = Usuario.objects.filter(
            Q(nombre_usuario=identifier) | Q(correo=identifier)
        ).first()
        if not user:
            return Response(
                {"detail": "Usuario o contraseña incorrectos."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            valid_password = check_password(password, user.contrasenia)
        except (TypeError, ValueError):
            valid_password = False
        if not valid_password and user.contrasenia == password:
            user.contrasenia = make_password(password)
            user.save(update_fields=["contrasenia"])
            valid_password = True
        if not valid_password:
            return Response(
                {"detail": "Usuario o contraseña incorrectos."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if (user.estado or "").casefold() != "activo":
            return Response(
                {"detail": "Esta cuenta se encuentra inactiva."},
                status=status.HTTP_403_FORBIDDEN,
            )

        role = mobile_role_for_user(user)
        if role is None:
            return Response(
                {"detail": "La app está habilitada para padres/tutores y administradores."},
                status=status.HTTP_403_FORBIDDEN,
            )

        MobileSession.objects.filter(expires_at__lte=timezone.now()).delete()
        access = create_access_token(user.pk, role)
        return Response(
            {
                "access": access,
                "token_type": "Bearer",
                "expires_in": TOKEN_TTL_SECONDS,
                "user": user_payload(user, role),
            }
        )


class CurrentUserView(APIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request):
        return Response(
            {"user": user_payload(request.user, request.auth["role"])}
        )


class LogoutView(APIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def post(self, request):
        MobileSession.objects.filter(
            jti=request.auth["jti"],
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeView(APIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mobile_password_change"

    def post(self, request):
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")
        if (
            not isinstance(current_password, str)
            or not current_password
            or len(current_password) > 256
            or not isinstance(new_password, str)
            or not new_password
            or len(new_password) > 256
        ):
            return Response(
                {"detail": "Ingresá contraseñas válidas de hasta 256 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            password_actual_valida = check_password(
                current_password,
                request.user.contrasenia,
            )
        except (TypeError, ValueError):
            password_actual_valida = False
        if not password_actual_valida:
            return Response(
                {"detail": "La contraseña actual es incorrecta."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if check_password(new_password, request.user.contrasenia):
            return Response(
                {"detail": "La nueva contraseña debe ser distinta de la actual."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario_para_validacion = SimpleNamespace(
            username=request.user.nombre_usuario,
            email=request.user.correo or "",
        )
        try:
            validate_password(new_password, user=usuario_para_validacion)
        except ValidationError as exc:
            return Response(
                {"detail": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            request.user.contrasenia = make_password(new_password)
            request.user.save(update_fields=["contrasenia"])
            MobileSession.objects.filter(
                user_id=request.user.pk,
                revoked_at__isnull=True,
            ).exclude(jti=request.auth["jti"]).update(revoked_at=timezone.now())

        return Response({"detail": "La contraseña se cambió correctamente."})


def _password_reset_digest(reset, code):
    message = f"{reset.pk}:{reset.user_id}:{code}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()


class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mobile_recovery_request"

    generic_response = {
        "detail": "Si existe una cuenta activa con ese correo, enviaremos un código de recuperación válido por 15 minutos."
    }

    def post(self, request):
        email = request.data.get("email")
        if not isinstance(email, str) or not email.strip() or len(email.strip()) > 100:
            return Response(self.generic_response)

        user = Usuario.objects.filter(correo__iexact=email.strip()).first()
        if (
            user is None
            or (user.estado or "").casefold() != "activo"
            or mobile_role_for_user(user) is None
        ):
            return Response(self.generic_response)

        now = timezone.now()
        code = f"{secrets.randbelow(1_000_000):06d}"
        with transaction.atomic():
            MobilePasswordReset.objects.filter(
                user=user,
                used_at__isnull=True,
            ).update(used_at=now)
            reset = MobilePasswordReset.objects.create(
                user=user,
                code_digest="",
                expires_at=now + timedelta(minutes=15),
            )
            reset.code_digest = _password_reset_digest(reset, code)
            reset.save(update_fields=["code_digest"])

        try:
            send_mail(
                subject="Código para recuperar tu contraseña",
                message=(
                    f"Hola {user.nombre_usuario},\n\n"
                    f"Tu código para recuperar el acceso es: {code}\n\n"
                    "Vence en 15 minutos y solo puede usarse una vez. "
                    "Si no solicitaste este cambio, ignorá este mensaje."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.correo],
                fail_silently=False,
            )
        except Exception:
            MobilePasswordReset.objects.filter(pk=reset.pk).update(used_at=timezone.now())
            logger.exception("No se pudo enviar el correo de recuperación móvil.")

        return Response(self.generic_response)


class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mobile_recovery_confirm"

    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")
        new_password = request.data.get("new_password")
        if (
            not isinstance(email, str)
            or not email.strip()
            or len(email.strip()) > 100
            or not isinstance(code, str)
            or len(code) != 6
            or not code.isdigit()
            or not isinstance(new_password, str)
            or not new_password
            or len(new_password) > 256
        ):
            return Response(
                {"detail": "Ingresá correo, código y una nueva contraseña válida."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        with transaction.atomic():
            reset = (
                MobilePasswordReset.objects.select_for_update()
                .select_related("user")
                .filter(
                    user__correo__iexact=email.strip(),
                    used_at__isnull=True,
                    expires_at__gt=now,
                    failed_attempts__lt=5,
                )
                .order_by("-created_at")
                .first()
            )
            if (
                reset is None
                or (reset.user.estado or "").casefold() != "activo"
                or not hmac.compare_digest(
                    reset.code_digest,
                    _password_reset_digest(reset, code),
                )
            ):
                if reset is not None:
                    reset.failed_attempts += 1
                    if reset.failed_attempts >= 5:
                        reset.used_at = now
                    reset.save(update_fields=["failed_attempts", "used_at"])
                return Response(
                    {"detail": "El código es incorrecto o venció. Solicitá uno nuevo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if check_password(new_password, reset.user.contrasenia):
                return Response(
                    {"detail": "La nueva contraseña debe ser distinta de la actual."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            usuario_para_validacion = SimpleNamespace(
                username=reset.user.nombre_usuario,
                email=reset.user.correo or "",
            )
            try:
                validate_password(new_password, user=usuario_para_validacion)
            except ValidationError as exc:
                return Response(
                    {"detail": exc.messages},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            reset.user.contrasenia = make_password(new_password)
            reset.user.save(update_fields=["contrasenia"])
            reset.used_at = now
            reset.save(update_fields=["used_at"])
            MobilePasswordReset.objects.filter(
                user=reset.user,
                used_at__isnull=True,
            ).exclude(pk=reset.pk).update(used_at=now)
            MobileSession.objects.filter(
                user_id=reset.user_id,
                revoked_at__isnull=True,
            ).update(revoked_at=now)

        return Response({"detail": "La contraseña se restableció. Iniciá sesión con la nueva contraseña."})


class AdminNotificationSimulationView(APIView):
    """Send one administrator-only sample of a scheduled parent notification."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mobile_notification_simulation"

    def post(self, request):
        if request.auth.get("role") != "administrativo":
            return Response(
                {"detail": "Esta función está disponible solo para administración."},
                status=status.HTTP_403_FORBIDDEN,
            )

        test_recipient = os.environ.get("ADMIN_NOTIFICATION_EMAIL", "").strip()
        if test_recipient.casefold() != "maxecheverri9@gmail.com":
            return Response(
                {"detail": "Configurá ADMIN_NOTIFICATION_EMAIL como maxecheverri9@gmail.com para habilitar la prueba segura."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        tipo = request.data.get("tipo")
        if tipo not in {"factura", "recordatorio"}:
            return Response(
                {"detail": "Elegí factura o recordatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            mes = int(request.data.get("mes"))
            anio = int(request.data.get("anio"))
            legajo = int(request.data.get("legajo"))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Período y legajo deben ser números válidos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not 1 <= mes <= 12 or not 2000 <= anio <= 9999 or legajo <= 0:
            return Response(
                {"detail": "Revisá el mes, año y legajo indicados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        alumno = Alumno.objects.filter(legajo=legajo).select_related(
            "id_persona",
            "id_curso__nivel_educativo",
        ).first()
        if alumno is None:
            return Response(
                {"detail": "No se encontró un alumno con ese legajo."},
                status=status.HTTP_404_NOT_FOUND,
            )

        relacion = TutorTutoraAlumno.objects.filter(id_alumno=alumno).select_related(
            "id_tutor__id_persona__id_usuario",
        ).first()
        if relacion is None or relacion.id_tutor is None:
            return Response(
                {"detail": "El alumno no tiene un tutor asociado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        periodo = f"{MESES_SIMULACION[mes - 1]} {anio}"
        nombre_alumno = f"{alumno.id_persona.nombre} {alumno.id_persona.apellido}".strip()
        if tipo == "factura":
            resultado = self._enviar_factura(
                alumno=alumno,
                tutor=relacion.id_tutor,
                nombre_alumno=nombre_alumno,
                periodo=periodo,
                mes=mes,
                anio=anio,
                test_recipient=test_recipient,
            )
        else:
            resultado = self._enviar_recordatorio(
                alumno=alumno,
                tutor=relacion.id_tutor,
                periodo=periodo,
                mes=mes,
                anio=anio,
                test_recipient=test_recipient,
            )

        if isinstance(resultado, Response):
            return resultado
        return Response({
            "detail": resultado["detail"],
            "destinatario": test_recipient,
            "tipo": tipo,
            "periodo": periodo,
            "alumno": nombre_alumno,
            "total": resultado.get("total"),
        })

    @staticmethod
    def _enviar_factura(alumno, tutor, nombre_alumno, periodo, mes, anio, test_recipient):
        from core.cuota_conceptos import construir_conceptos_cuota
        from core.factura_pdf import formatear_moneda, generar_factura_pdf

        nivel = (
            alumno.id_curso.nivel_educativo.nombre
            if alumno.id_curso and alumno.id_curso.nivel_educativo_id
            else "General"
        )
        equivalencias_nivel = {
            "inicial": "inicial",
            "primaria": "primario",
            "primario": "primario",
            "secundaria": "secundario",
        }
        nivel_clave = nivel.strip().casefold()
        nivel_normalizado = equivalencias_nivel.get(nivel_clave, nivel_clave)
        aranceles = [
            arancel.monto
            for arancel in Arancel.objects.all().order_by("id_arancel")
            if equivalencias_nivel.get(
                arancel.nivel.strip().casefold(), arancel.nivel.strip().casefold()
            ) == nivel_normalizado
        ]
        monto_base = aranceles[0] if aranceles else Decimal("30000.00")
        desglose = construir_conceptos_cuota(alumno, monto_base, nivel=nivel)
        total = sum((Decimal(str(item["monto"])) for item in desglose), Decimal("0.00"))
        cuota_simulada = SimpleNamespace(
            id_cuota=0,
            periodo=periodo,
            fecha_vencimiento=date(anio, mes, 10),
            total_obligacion=total,
            monto_pagado_actual=lambda: Decimal("0.00"),
        )
        archivo_pdf = generar_factura_pdf(
            cuota=cuota_simulada,
            alumno=alumno,
            tutor=tutor,
            desglose_conceptos=desglose,
            numero_factura=f"PRUEBA-{anio}{mes:02d}-{alumno.legajo:05d}",
            fecha_emision=timezone.localdate().strftime("%d/%m/%Y"),
        )
        correo = EmailMessage(
            subject=f"[PRUEBA] Factura de Aranceles {periodo} - {nombre_alumno}",
            body=(
                "Este correo de prueba simula la factura mensual programada.\n"
                f"\nAlumno: {nombre_alumno}\nPeríodo: {periodo}\n"
                f"Total simulado: {formatear_moneda(total)}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[test_recipient],
        )
        correo.attach(f"factura_prueba_{anio}_{mes:02d}_{alumno.legajo}.pdf", archivo_pdf, "application/pdf")
        return AdminNotificationSimulationView._send(correo, total)

    @staticmethod
    def _enviar_recordatorio(alumno, tutor, periodo, mes, anio, test_recipient):
        from core.factura_pdf import formatear_moneda

        legajos_tutor = TutorTutoraAlumno.objects.filter(
            id_tutor=tutor,
        ).values_list("id_alumno_id", flat=True)
        cuotas = Cuota.objects.filter(
            id_tutor=tutor,
            id_legajo_alumno_id__in=legajos_tutor,
        ).select_related("id_legajo_alumno__id_persona").prefetch_related(
            "pagos",
            "comprobantes__pago",
        )

        detalle = []
        for cuota in cuotas:
            saldo = max(
                (cuota.total_obligacion or Decimal("0.00")) - cuota.monto_pagado_actual(),
                Decimal("0.00"),
            )
            if saldo <= 0:
                continue
            en_revision = Decimal("0.00")
            for comprobante in cuota.comprobantes.all():
                if comprobante.pago and (comprobante.pago.estado or "").casefold() == "en revisión":
                    en_revision += comprobante.pago.importe or Decimal("0.00")
                elif (comprobante.estado or "").casefold() == "en revisión":
                    en_revision += saldo
            saldo_neto = max(saldo - min(en_revision, saldo), Decimal("0.00"))
            if saldo_neto > 0:
                persona = cuota.id_legajo_alumno.id_persona
                nombre = f"{persona.nombre} {persona.apellido}".strip()
                detalle.append((nombre, cuota, saldo_neto))

        if not detalle:
            return Response(
                {"detail": "Ese tutor no tiene saldo pendiente fuera de revisión para el período."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total = sum((saldo for _, _, saldo in detalle), Decimal("0.00"))
        lineas = [
            f"• {nombre} — {cuota.periodo}: {formatear_moneda(saldo)}"
            for nombre, cuota, saldo in detalle
        ]
        persona_tutor = tutor.id_persona
        nombre_tutor = f"{persona_tutor.nombre} {persona_tutor.apellido}".strip()
        correo = EmailMessage(
            subject=f"[PRUEBA] Recordatorio de deuda - {periodo}",
            body=(
                "Este correo de prueba simula el recordatorio programado del día 20.\n"
                f"\nTutor: {nombre_tutor}\nMes de la prueba: {periodo}\n\n"
                f"{chr(10).join(lineas)}\n\n"
                f"Total pendiente simulado: {formatear_moneda(total)}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[test_recipient],
        )
        return AdminNotificationSimulationView._send(correo, total)

    @staticmethod
    def _send(correo, total):
        try:
            sent = correo.send(fail_silently=False)
        except Exception:
            logger.exception("No se pudo enviar el correo de simulación de notificación.")
            return Response(
                {"detail": "No se pudo enviar la copia de prueba. Revisá la configuración de correo."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        if sent != 1:
            return Response(
                {"detail": "El servicio de correo no confirmó el envío de la copia de prueba."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return {"detail": "Correo de prueba enviado al correo administrativo. No se cambiaron datos financieros.", "total": str(total)}


class CuotasView(APIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request):
        if request.auth.get("role") != "padre":
            return Response(
                {"detail": "Este recurso está disponible para padres/tutores."},
                status=status.HTTP_403_FORBIDDEN,
            )

        tutor = Tutor.objects.filter(id_persona__id_usuario=request.user).first()
        if tutor is None:
            return Response(
                {"detail": "No se encontró el perfil de tutor asociado a la cuenta."},
                status=status.HTTP_403_FORBIDDEN,
            )

        legajos_hijos = TutorTutoraAlumno.objects.filter(
            id_tutor=tutor
        ).values_list("id_alumno_id", flat=True)

        cuotas = Cuota.objects.filter(
            id_tutor=tutor,
            id_legajo_alumno_id__in=legajos_hijos,
        ).select_related(
            "id_legajo_alumno__id_persona",
            "id_legajo_alumno__id_curso__nivel_educativo",
        ).prefetch_related(
            "pagos",
            "comprobantes__pago__solicitud",
        ).order_by("-fecha_vencimiento", "-id_cuota")

        periodo = request.query_params.get("periodo")
        if periodo:
            cuotas = cuotas.filter(periodo__iexact=periodo.strip())

        estado = request.query_params.get("estado")
        estados_validos = {
            "pendiente": "Pendiente",
            "parcial": "Parcial",
            "pagada": "Pagada",
            "vencida": "Vencida",
        }
        if estado:
            estado_normalizado = estado.strip().casefold()
            if estado_normalizado not in estados_validos:
                return Response(
                    {"detail": "El filtro estado debe ser pendiente, parcial, pagada o vencida."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            estado = estados_validos[estado_normalizado]
        else:
            estado = None

        data = []
        for cuota in cuotas:
            alumno = cuota.id_legajo_alumno
            persona = alumno.id_persona
            curso = alumno.id_curso
            nombre_curso = ""
            if curso:
                nivel = curso.nivel_educativo.nombre
                nombre_curso = f"{curso.anio}° Año {curso.comision} - {nivel}"

            total = cuota.total_obligacion or Decimal("0")
            monto_pagado = cuota.monto_pagado_actual()
            saldo = max(total - monto_pagado, Decimal("0"))
            if saldo <= 0 and total > 0:
                estado_cuota = "pagada"
            elif monto_pagado > 0:
                estado_cuota = "parcial"
            elif cuota.fecha_vencimiento and cuota.fecha_vencimiento < timezone.localdate():
                estado_cuota = "vencida"
            else:
                estado_cuota = "pendiente"
            if estado and estado_cuota != estado.casefold():
                continue
            data.append(
                {
                    "id": cuota.id_cuota,
                    "periodo": cuota.periodo,
                    "monto_total": str(total),
                    "monto": str(total),
                    "monto_pagado": str(monto_pagado),
                    "saldo": str(saldo),
                    "fecha_vencimiento": cuota.fecha_vencimiento.isoformat() if cuota.fecha_vencimiento else None,
                    "fecha_pago": cuota.fecha_pago.isoformat() if cuota.fecha_pago else None,
                    "estado": estado_cuota,
                    "discriminacion": _discriminacion_cuota(cuota),
                    "conceptos_pago": _conceptos_pago_cuota(cuota, saldo),
                    "comprobantes": [
                        {
                            "id": comprobante.id_comprobante,
                            "estado": comprobante.estado.casefold(),
                            "estado_pago": (
                                comprobante.pago.estado.casefold()
                                if comprobante.pago
                                else comprobante.estado.casefold()
                            ),
                            "fecha_envio": comprobante.fecha_envio.isoformat(),
                            "importe": (
                                str(comprobante.pago.importe)
                                if comprobante.pago
                                else None
                            ),
                            "motivo_rechazo": (
                                comprobante.pago.solicitud.motivo_rechazo
                                if comprobante.pago and comprobante.pago.solicitud_id
                                else None
                            ),
                            "nombre_archivo": comprobante.archivo.name,
                        }
                        for comprobante in cuota.comprobantes.all()
                    ],
                    "alumno": {
                        "legajo": alumno.legajo,
                        "nombre_completo": f"{persona.nombre} {persona.apellido}".strip(),
                        "curso": nombre_curso,
                    },
                }
            )

        return Response(data)


class CuotaDetalleView(APIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request, cuota_id):
        response = CuotasView().get(request)
        if response.status_code != status.HTTP_200_OK:
            return response
        cuota = next((item for item in response.data if item["id"] == cuota_id), None)
        if cuota is None:
            return Response({"detail": "Cuota no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        return Response(cuota)


class ServiciosInscripcionesView(APIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request):
        if request.auth.get("role") != "padre":
            return Response(
                {"detail": "Este recurso está disponible para padres/tutores."},
                status=status.HTTP_403_FORBIDDEN,
            )

        tutor = Tutor.objects.filter(id_persona__id_usuario=request.user).first()
        if tutor is None:
            return Response(
                {"detail": "No se encontró el perfil de tutor asociado a la cuenta."},
                status=status.HTTP_403_FORBIDDEN,
            )

        legajos_hijos = TutorTutoraAlumno.objects.filter(
            id_tutor=tutor,
        ).values_list("id_alumno_id", flat=True)
        alumnos = Alumno.objects.filter(
            legajo__in=legajos_hijos,
        ).select_related(
            "id_persona",
        ).prefetch_related(
            "inscripciones_deportivas__id_grupo__id_disciplina",
            "inscripciones_deportivas__id_grupo__horarios_normalizados",
            "inscripciones_transporte__id_recorrido",
            "inscripciones_comedor__id_servicio",
        ).order_by("id_persona__apellido", "id_persona__nombre")

        data = []
        for alumno in alumnos:
            persona = alumno.id_persona
            deportes = []
            for inscripcion in alumno.inscripciones_deportivas.all():
                grupo = inscripcion.id_grupo
                if inscripcion.estado.casefold() != "activa" or grupo.estado.casefold() != "activo":
                    continue
                horarios = list(grupo.horarios_normalizados.all())
                horario = ", ".join(
                    f"{item.dia_semana} {item.hora_inicio.strftime('%H:%M')}-{item.hora_fin.strftime('%H:%M')}"
                    for item in horarios
                ) or (
                    f"{grupo.dia_semana} "
                    f"{grupo.hora_inicio.strftime('%H:%M')}-{grupo.hora_fin.strftime('%H:%M')}"
                )
                deportes.append({
                    "id": inscripcion.id_inscripcion,
                    "nombre": grupo.id_disciplina.nombre,
                    "monto_mensual": str(grupo.id_disciplina.monto_mensual),
                    "horario": horario,
                    "estado": inscripcion.estado,
                })

            transporte = None
            for inscripcion in alumno.inscripciones_transporte.all():
                if (
                    inscripcion.estado.casefold() == "activa"
                    and inscripcion.id_recorrido.estado.casefold() == "activo"
                ):
                    transporte = {
                        "id_inscripcion": inscripcion.id_inscripcion,
                        "recorrido": inscripcion.id_recorrido.nombre,
                        "monto_mensual": str(inscripcion.id_recorrido.monto_mensual),
                        "estado": inscripcion.estado,
                    }
                    break

            comedor = None
            for inscripcion in alumno.inscripciones_comedor.all():
                if (
                    inscripcion.estado.casefold() == "activa"
                    and inscripcion.id_servicio.estado.casefold() == "activo"
                ):
                    comedor = {
                        "id_inscripcion": inscripcion.id_inscripcion,
                        "servicio": inscripcion.id_servicio.nombre,
                        "monto_mensual": str(inscripcion.id_servicio.monto_mensual),
                        "estado": inscripcion.estado,
                    }
                    break

            data.append({
                "alumno": {
                    "legajo": alumno.legajo,
                    "nombre_completo": f"{persona.nombre} {persona.apellido}".strip(),
                },
                "deportes": deportes,
                "transporte": transporte,
                "comedor": comedor,
            })
        return Response(data)


class ComprobantesView(APIView):
    """Recibe un comprobante y lo deja en el flujo administrativo existente."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if request.auth.get("role") != "padre":
            return Response(
                {"detail": "Este recurso está disponible para padres/tutores."},
                status=status.HTTP_403_FORBIDDEN,
            )

        tutor = Tutor.objects.filter(id_persona__id_usuario=request.user).first()
        if tutor is None:
            return Response({"detail": "No se encontró el perfil de tutor."}, status=status.HTTP_403_FORBIDDEN)

        try:
            cuota_id = int(request.data.get("cuota_id"))
            importe = Decimal(str(request.data.get("importe", "")))
        except (TypeError, ValueError, InvalidOperation):
            return Response({"detail": "cuota_id e importe son obligatorios y válidos."}, status=status.HTTP_400_BAD_REQUEST)

        archivo = request.FILES.get("archivo")
        if not archivo:
            return Response({"detail": "Debe enviar el archivo del comprobante en 'archivo'."}, status=status.HTTP_400_BAD_REQUEST)
        if importe <= 0:
            return Response({"detail": "El importe debe ser mayor que cero."}, status=status.HTTP_400_BAD_REQUEST)

        seleccion_informada = "conceptos_seleccionados" in request.data
        seleccion_raw = request.data.get("conceptos_seleccionados")
        seleccion = None
        if seleccion_informada:
            try:
                seleccion = json.loads(seleccion_raw) if isinstance(seleccion_raw, str) else seleccion_raw
            except (TypeError, ValueError):
                return Response({"detail": "conceptos_seleccionados debe ser una lista JSON válida."}, status=status.HTTP_400_BAD_REQUEST)
            if not isinstance(seleccion, list) or not seleccion or any(not isinstance(item, str) for item in seleccion):
                return Response({"detail": "Seleccione al menos un concepto válido para pagar."}, status=status.HTTP_400_BAD_REQUEST)
            if len(seleccion) != len(set(seleccion)):
                return Response({"detail": "No repita conceptos en la selección."}, status=status.HTTP_400_BAD_REQUEST)

        legajos_hijos = TutorTutoraAlumno.objects.filter(id_tutor=tutor).values_list("id_alumno_id", flat=True)
        with transaction.atomic():
            cuota = Cuota.objects.select_for_update().filter(
                id_cuota=cuota_id,
                id_tutor=tutor,
                id_legajo_alumno_id__in=legajos_hijos,
            ).first()
            if cuota is None:
                return Response({"detail": "La cuota no existe o no pertenece a un alumno asociado."}, status=status.HTTP_404_NOT_FOUND)

            saldo = max((cuota.total_obligacion or Decimal("0")) - cuota.monto_pagado_actual(), Decimal("0"))
            if importe > saldo:
                return Response({"detail": "El importe supera el saldo pendiente de la cuota.", "saldo": str(saldo)}, status=status.HTTP_400_BAD_REQUEST)

            conceptos_aplicados = {}
            if seleccion_informada:
                conceptos_disponibles = disponibilidad_conceptos_pago(cuota)
                if seleccion == ["__saldo_total__"] and not conceptos_disponibles:
                    conceptos_historicos = _conceptos_pago_cuota(cuota, saldo)
                    importe_esperado = Decimal(conceptos_historicos[0]["saldo_disponible"])
                    if importe != importe_esperado or importe_esperado <= 0:
                        return Response({"detail": "Para esta cuota histórica debe abonarse el saldo completo disponible.", "saldo": str(importe_esperado)}, status=status.HTTP_400_BAD_REQUEST)
                    conceptos_aplicados = {"__saldo_total__": str(importe_esperado)}
                else:
                    conceptos_disponibles = {
                        item["clave"]: Decimal(str(item["saldo_disponible"]))
                        for item in conceptos_disponibles
                    }
                    if any(clave not in conceptos_disponibles for clave in seleccion):
                        return Response({"detail": "La selección contiene conceptos que no pertenecen a esta cuota."}, status=status.HTTP_400_BAD_REQUEST)
                    importes_conceptos = {
                        clave: conceptos_disponibles[clave]
                        for clave in seleccion
                    }
                    if any(monto <= 0 for monto in importes_conceptos.values()):
                        return Response({"detail": "Uno o más conceptos ya están pagados o en revisión."}, status=status.HTTP_400_BAD_REQUEST)
                    importe_esperado = sum(importes_conceptos.values(), Decimal("0.00"))
                    if importe != importe_esperado:
                        return Response({
                            "detail": "El importe debe coincidir con el saldo completo de los conceptos seleccionados.",
                            "importe_esperado": str(importe_esperado),
                        }, status=status.HTTP_400_BAD_REQUEST)
                    conceptos_aplicados = {
                        clave: str(monto)
                        for clave, monto in importes_conceptos.items()
                    }

            solicitud = PagoPendiente.objects.create(
                id_tutor=tutor,
                legajo_alumno=cuota.id_legajo_alumno,
                mes=cuota.periodo,
                importe=importe,
                estado="En revisión",
                fecha_solicitud=timezone.now(),
            )
            pago = PagoCuota.objects.create(
                cuota=cuota,
                solicitud=solicitud,
                tutor=tutor,
                importe=importe,
                medio_pago=request.data.get("medio_pago") or "Transferencia",
                conceptos_aplicados=conceptos_aplicados,
                estado="En revisión",
            )
            comprobante = ComprobantePago.objects.create(
                cuota=cuota,
                pago=pago,
                archivo=archivo,
            )

        return Response(
            {
                "id": comprobante.id_comprobante,
                "cuota_id": cuota.id_cuota,
                "pago_id": pago.id_pago,
                "estado": "en revisión",
                "mensaje": "El comprobante fue enviado y queda pendiente de revisión administrativa.",
            },
            status=status.HTTP_201_CREATED,
        )


class ComprobanteArchivoView(APIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request, comprobante_id):
        role = request.auth.get("role")
        if role == "administrativo":
            comprobante = ComprobantePago.objects.filter(id_comprobante=comprobante_id).first()
        elif role == "padre":
            tutor = Tutor.objects.filter(id_persona__id_usuario=request.user).first()
            legajos_hijos = TutorTutoraAlumno.objects.filter(id_tutor=tutor).values_list("id_alumno_id", flat=True)
            comprobante = ComprobantePago.objects.filter(
                id_comprobante=comprobante_id,
                cuota__id_tutor=tutor,
                cuota__id_legajo_alumno_id__in=legajos_hijos,
            ).first()
        else:
            return Response({"detail": "No autorizado para este recurso."}, status=status.HTTP_403_FORBIDDEN)

        if comprobante is None or not comprobante.archivo:
            return Response({"detail": "Comprobante no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        try:
            archivo = comprobante.archivo.open("rb")
        except FileNotFoundError:
            return Response({"detail": "El archivo del comprobante no está disponible."}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(archivo, as_attachment=False, filename=comprobante.archivo.name.rsplit("/", 1)[-1])


class AdminComprobantesPendientesView(APIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request):
        if request.auth.get("role") != "administrativo":
            return Response({"detail": "Este recurso está disponible para administración."}, status=status.HTTP_403_FORBIDDEN)

        pagos = (
            PagoPendiente.objects.select_related(
                "id_tutor__id_persona",
                "id_tutor__id_persona__id_usuario",
                "legajo_alumno__id_persona",
                "legajo_alumno__id_curso",
            )
            .prefetch_related(
                "pago_aplicado__comprobantes",
                "pago_aplicado__cuota",
            )
            .filter(estado__in=["En revisión", "Pendiente"])
            .order_by("-fecha_solicitud", "-id_pago")
        )

        data = []
        for pago in pagos:
            persona_alumno = getattr(pago.legajo_alumno, "id_persona", None)
            nombre_alumno = f"{persona_alumno.nombre} {persona_alumno.apellido}".strip() if persona_alumno else "Alumno"
            curso_alumno = str(pago.legajo_alumno.id_curso) if pago.legajo_alumno and pago.legajo_alumno.id_curso else ""

            persona_tutor = getattr(pago.id_tutor, "id_persona", None)
            nombre_tutor = f"{persona_tutor.nombre} {persona_tutor.apellido}".strip() if persona_tutor else "Tutor"
            usuario_tutor = getattr(persona_tutor, "id_usuario", None) if persona_tutor else None
            email_tutor = (getattr(usuario_tutor, "correo", "") or getattr(pago.id_tutor, "email_contacto", "") or "").strip()

            pago_aplicado = getattr(pago, "pago_aplicado", None)
            comprobante_obj = pago_aplicado.comprobantes.first() if pago_aplicado else None
            comprobante_data = None
            if comprobante_obj and comprobante_obj.archivo:
                comprobante_data = {
                    "id": comprobante_obj.id_comprobante,
                    "nombre_archivo": comprobante_obj.archivo.name.rsplit("/", 1)[-1],
                    "archivo_url": f"/api/comprobantes/{comprobante_obj.id_comprobante}/archivo/",
                    "fecha_envio": comprobante_obj.fecha_envio.isoformat() if comprobante_obj.fecha_envio else None,
                }

            conceptos_aplicados = pago_aplicado.conceptos_aplicados if pago_aplicado and isinstance(pago_aplicado.conceptos_aplicados, dict) else {}
            conceptos_detalle = []
            if pago_aplicado and pago_aplicado.cuota and pago_aplicado.cuota.conceptos:
                conceptos_por_clave = {
                    clave_concepto(c): c.get("concepto", "Concepto")
                    for c in pago_aplicado.cuota.conceptos
                    if isinstance(c, dict)
                }
                for k, m in conceptos_aplicados.items():
                    conceptos_detalle.append({
                        "clave": k,
                        "concepto": conceptos_por_clave.get(k, k),
                        "monto": str(m),
                    })
            elif conceptos_aplicados:
                for k, m in conceptos_aplicados.items():
                    conceptos_detalle.append({
                        "clave": k,
                        "concepto": "Saldo total de la cuota" if k == "__saldo_total__" else k,
                        "monto": str(m),
                    })

            data.append({
                "id": pago.id_pago,
                "cuota_id": pago_aplicado.cuota_id if pago_aplicado else None,
                "periodo": pago.mes,
                "importe": str(pago.importe),
                "estado": pago.estado,
                "fecha_solicitud": pago.fecha_solicitud.isoformat() if pago.fecha_solicitud else None,
                "motivo_rechazo": pago.motivo_rechazo,
                "alumno": {
                    "legajo": pago.legajo_alumno_id,
                    "nombre": nombre_alumno,
                    "curso": curso_alumno,
                },
                "tutor": {
                    "id": pago.id_tutor_id,
                    "nombre": nombre_tutor,
                    "email": email_tutor,
                },
                "comprobante": comprobante_data,
                "conceptos": conceptos_detalle,
            })
        return Response(data)


class AdminComprobanteAprobarView(APIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def post(self, request, pago_id):
        if request.auth.get("role") != "administrativo":
            return Response({"detail": "Este recurso está disponible para administración."}, status=status.HTTP_403_FORBIDDEN)

        from core.views import _enviar_confirmacion_pago_aprobado

        with transaction.atomic():
            pago = PagoPendiente.objects.select_for_update().filter(id_pago=pago_id).first()
            if pago is None:
                return Response({"detail": "Pago pendiente no encontrado."}, status=status.HTTP_404_NOT_FOUND)

            if pago.estado == "Pagado":
                return Response({"detail": "El pago ya se encuentra aprobado.", "pago_id": pago.id_pago, "estado": "Pagado"})

            if pago.estado == "Rechazado":
                return Response({"detail": "No se puede aprobar un pago que fue rechazado."}, status=status.HTTP_400_BAD_REQUEST)

            cuota = Cuota.objects.select_for_update().filter(
                id_tutor=pago.id_tutor,
                id_legajo_alumno=pago.legajo_alumno,
                periodo=pago.mes,
            ).order_by("-id_cuota").first()

            if cuota is None:
                cuota = Cuota.objects.create(
                    periodo=pago.mes,
                    monto=pago.importe,
                    monto_total=pago.importe,
                    fecha_pago=timezone.localdate(),
                    medio_pago="Transferencia",
                    estado="Pendiente",
                    id_tutor=pago.id_tutor,
                    id_legajo_alumno=pago.legajo_alumno,
                )

            try:
                pago_aplicado = pago.pago_aplicado
            except PagoCuota.DoesNotExist:
                pago_aplicado = None

            if pago_aplicado is None:
                pago_aplicado = PagoCuota.objects.create(
                    cuota=cuota,
                    solicitud=pago,
                    tutor=pago.id_tutor,
                    importe=pago.importe,
                    fecha_pago=timezone.localdate(),
                    medio_pago="Transferencia",
                    estado="Pagado",
                )
            elif pago_aplicado.estado != "Pagado":
                pago_aplicado.estado = "Pagado"
                pago_aplicado.fecha_pago = timezone.localdate()
                pago_aplicado.save(update_fields=["estado", "fecha_pago"])

            ComprobantePago.objects.filter(pago=pago_aplicado).update(estado="Aprobado")
            pago.estado = "Pagado"
            pago.save(update_fields=["estado"])
            cuota.fecha_pago = timezone.localdate()
            cuota.save(update_fields=["fecha_pago"])
            cuota.actualizar_estado()

            persona_alumno = pago.legajo_alumno.id_persona
            nombre_alumno = f"{persona_alumno.nombre} {persona_alumno.apellido}".strip()
            persona_tutor = pago.id_tutor.id_persona
            usuario_tutor = getattr(persona_tutor, "id_usuario", None)
            destinatario = (
                getattr(usuario_tutor, "correo", "")
                or getattr(pago.id_tutor, "email_contacto", "")
                or ""
            ).strip()
            saldo_restante = max(
                (cuota.total_obligacion or Decimal("0.00")) - cuota.monto_pagado_actual(),
                Decimal("0.00"),
            )
            estado_cuota = cuota.estado
            asunto = f"Pago aprobado - {nombre_alumno} - {cuota.periodo}"
            cuerpo = (
                f"Estimado/a {persona_tutor.nombre} {persona_tutor.apellido}:\n\n"
                f"Administración aprobó el pago informado para {nombre_alumno}.\n\n"
                f"Período: {cuota.periodo}\n"
                f"Importe aprobado: {pago.importe}\n"
                f"Estado de la cuota: {estado_cuota}\n"
                f"Saldo restante: {saldo_restante}\n\n"
                "Adjuntamos el comprobante PDF del pago aprobado. También podés consultar el estado "
                "desde la aplicación móvil o el portal.\n\n"
                "Administración Escolar\nCentro Educativo «Transformar para educar»"
            )
            transaction.on_commit(
                lambda: _enviar_confirmacion_pago_aprobado(
                    destinatario,
                    asunto,
                    cuerpo,
                    pago_aplicado.id_pago,
                )
            )

        return Response({
            "detail": "Pago aprobado con éxito.",
            "pago_id": pago.id_pago,
            "estado": "Pagado",
            "cuota_estado": cuota.estado,
        })


class AdminComprobanteRechazarView(APIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def post(self, request, pago_id):
        if request.auth.get("role") != "administrativo":
            return Response({"detail": "Este recurso está disponible para administración."}, status=status.HTTP_403_FORBIDDEN)

        motivo = (request.data.get("motivo") or request.data.get("motivo_rechazo") or "").strip()
        if not motivo:
            return Response({"detail": "Debe indicar el motivo del rechazo."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            pago = PagoPendiente.objects.select_for_update().filter(id_pago=pago_id).first()
            if pago is None:
                return Response({"detail": "Pago pendiente no encontrado."}, status=status.HTTP_404_NOT_FOUND)

            if pago.estado == "Pagado":
                return Response({"detail": "No se puede rechazar un pago ya aprobado."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                pago_aplicado = pago.pago_aplicado
            except PagoCuota.DoesNotExist:
                pago_aplicado = None

            if pago_aplicado:
                pago_aplicado.estado = "Rechazado"
                pago_aplicado.save(update_fields=["estado"])
                ComprobantePago.objects.filter(pago=pago_aplicado).update(estado="Rechazado")

            pago.estado = "Rechazado"
            pago.motivo_rechazo = motivo
            pago.save(update_fields=["estado", "motivo_rechazo"])

            if pago_aplicado and pago_aplicado.cuota:
                pago_aplicado.cuota.actualizar_estado()

        return Response({
            "detail": "Pago rechazado correctamente.",
            "pago_id": pago.id_pago,
            "estado": "Rechazado",
            "motivo_rechazo": motivo,
        })


MESES_ESPANOL = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
)


def _periodo_reporte(request):
    hoy = timezone.localdate()
    try:
        mes = int(request.query_params.get("mes", hoy.month))
        anio = int(request.query_params.get("anio", hoy.year))
    except (TypeError, ValueError):
        return None
    if not 1 <= mes <= 12 or not 2000 <= anio <= 9999:
        return None
    return mes, anio


def _cuotas_del_periodo(mes, anio):
    periodo = f"{MESES_ESPANOL[mes - 1]} {anio}"
    return Cuota.objects.filter(
        Q(periodo__iexact=periodo)
        | Q(fecha_vencimiento__year=anio, fecha_vencimiento__month=mes)
    )


class ReporteIngresosView(APIView):
    """Reporte institucional de ingresos y recaudación para administradores (HU_M10)."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request):
        if request.auth.get("role") != "administrativo":
            return Response(
                {"detail": "Este reporte está disponible solo para el personal administrativo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        periodo = _periodo_reporte(request)
        if periodo is None:
            return Response(
                {"detail": "Parámetros inválidos. Use mes entre 1 y 12 y año desde 2000."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mes, anio = periodo
        cuotas = _cuotas_del_periodo(mes, anio).prefetch_related("pagos")

        total_facturado = sum((c.total_obligacion or Decimal("0") for c in cuotas), Decimal("0"))
        total_recaudado = sum((c.monto_pagado_actual() for c in cuotas), Decimal("0"))

        porcentaje = (
            round(float(total_recaudado / total_facturado * 100), 2)
            if total_facturado > 0
            else 0.0
        )

        ingresos_cuota_base = Decimal("0.00")
        ingresos_servicios = Decimal("0.00")
        reporte_desglose = agrupar_reporte_financiero(cuotas)
        for cuota in cuotas:
            asignados = distribuir_pago_por_conceptos(cuota)
            if asignados is None:
                continue
            for concepto, importe_pagado in asignados:
                if concepto.get("tipo") == "cuota_base":
                    ingresos_cuota_base += importe_pagado
                else:
                    ingresos_servicios += importe_pagado

        cantidad_cobradas = sum(
            1
            for c in cuotas
            if (c.estado or "").casefold() == "pagada"
            or (c.total_obligacion and c.monto_pagado_actual() >= c.total_obligacion)
        )
        cantidad_pendientes = len(cuotas) - cantidad_cobradas

        return Response({
            "mes": mes,
            "anio": anio,
            "total_recaudado": str(total_recaudado),
            "total_facturado": str(total_facturado),
            "porcentaje_cobranza": porcentaje,
            "ingresos_cuota_base": str(ingresos_cuota_base),
            "ingresos_servicios": str(ingresos_servicios),
            "ingresos_sin_desglose": reporte_desglose["pagado_sin_desglose"],
            "cuotas_sin_desglose": reporte_desglose["cuotas_sin_desglose"],
            "cantidad_cuotas_cobradas": cantidad_cobradas,
            "cantidad_cuotas_pendientes": max(cantidad_pendientes, 0),
        })


class ReportePagosCompletosView(APIView):
    """Listado de cuotas totalmente saldadas en un período para administradores (HU_M10)."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request):
        if request.auth.get("role") != "administrativo":
            return Response(
                {"detail": "Este reporte está disponible solo para el personal administrativo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        periodo = _periodo_reporte(request)
        if periodo is None:
            return Response(
                {"detail": "Parámetros inválidos. Use mes entre 1 y 12 y año desde 2000."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mes, anio = periodo
        hoy = timezone.localdate()

        cuotas = (
            _cuotas_del_periodo(mes, anio)
            .select_related(
                "id_legajo_alumno__id_persona",
                "id_legajo_alumno__id_curso__nivel_educativo",
                "id_tutor__id_persona",
            )
            .prefetch_related("pagos")
            .order_by("-fecha_vencimiento", "-id_cuota")
        )

        data = []
        for cuota in cuotas:
            total = cuota.total_obligacion or Decimal("0")
            pagado = cuota.monto_pagado_actual()
            if pagado < total or total <= Decimal("0"):
                continue

            alumno = cuota.id_legajo_alumno
            persona_alumno = alumno.id_persona
            curso = alumno.id_curso
            nombre_curso = (
                f"{curso.anio}° {curso.comision} - {curso.nivel_educativo.nombre}"
                if curso and curso.nivel_educativo
                else ""
            )
            persona_tutor = cuota.id_tutor.id_persona
            nombre_tutor = f"{persona_tutor.nombre} {persona_tutor.apellido}".strip() if persona_tutor else ""

            ultimo_pago = cuota.pagos.filter(estado="Pagado").order_by("-fecha_pago", "-id_pago").first()
            fecha_cancelacion = (
                cuota.fecha_pago.isoformat()
                if cuota.fecha_pago
                else (
                    ultimo_pago.fecha_pago.isoformat()
                    if (ultimo_pago and ultimo_pago.fecha_pago)
                    else (cuota.fecha_vencimiento.isoformat() if cuota.fecha_vencimiento else hoy.isoformat())
                )
            )
            medio_pago = (
                ultimo_pago.medio_pago
                if ultimo_pago and ultimo_pago.medio_pago
                else (cuota.medio_pago or "Transferencia bancaria")
            )

            data.append({
                "id": cuota.id_cuota,
                "alumno_legajo": alumno.legajo,
                "alumno_nombre": f"{persona_alumno.nombre} {persona_alumno.apellido}".strip(),
                "alumno_curso": nombre_curso,
                "tutor_nombre": nombre_tutor,
                "monto_total": str(total),
                "fecha_cancelacion": fecha_cancelacion,
                "medio_pago": medio_pago,
            })

        return Response(data)


class ReportePagosIncompletosView(APIView):
    """Listado de cuotas adeudadas o parciales en un período para administradores (HU_M10)."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request):
        if request.auth.get("role") != "administrativo":
            return Response(
                {"detail": "Este reporte está disponible solo para el personal administrativo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        periodo = _periodo_reporte(request)
        if periodo is None:
            return Response(
                {"detail": "Parámetros inválidos. Use mes entre 1 y 12 y año desde 2000."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mes, anio = periodo
        hoy = timezone.localdate()

        cuotas = (
            _cuotas_del_periodo(mes, anio)
            .select_related(
                "id_legajo_alumno__id_persona",
                "id_legajo_alumno__id_curso__nivel_educativo",
                "id_tutor__id_persona__id_usuario",
            )
            .prefetch_related("pagos")
            .order_by("-fecha_vencimiento", "-id_cuota")
        )

        data = []
        for cuota in cuotas:
            total = cuota.total_obligacion or Decimal("0")
            pagado = cuota.monto_pagado_actual()
            saldo = max(total - pagado, Decimal("0"))
            if saldo <= Decimal("0"):
                continue

            alumno = cuota.id_legajo_alumno
            persona_alumno = alumno.id_persona
            curso = alumno.id_curso
            nombre_curso = (
                f"{curso.anio}° {curso.comision} - {curso.nivel_educativo.nombre}"
                if curso and curso.nivel_educativo
                else ""
            )
            persona_tutor = cuota.id_tutor.id_persona
            nombre_tutor = f"{persona_tutor.nombre} {persona_tutor.apellido}".strip() if persona_tutor else ""
            tutor_email = (
                persona_tutor.id_usuario.correo
                if persona_tutor and getattr(persona_tutor, "id_usuario", None)
                else getattr(cuota.id_tutor, "email_contacto", "")
            ) or ""
            tutor_tel = getattr(cuota.id_tutor, "telefono_contacto", "") or (getattr(persona_tutor, "telefono", "") if persona_tutor else "")

            conceptos = [
                concepto.get("concepto")
                for concepto in (cuota.conceptos or [])
                if isinstance(concepto, dict) and concepto.get("concepto")
            ]
            if not conceptos:
                conceptos = ["Desglose histórico no disponible"]

            estado_cuota = (cuota.estado or "Pendiente").strip().casefold()
            if estado_cuota not in {"pagada", "parcial"} and cuota.fecha_vencimiento and cuota.fecha_vencimiento < hoy:
                estado_cuota = "vencida"

            data.append({
                "id": cuota.id_cuota,
                "alumno_legajo": alumno.legajo,
                "alumno_nombre": f"{persona_alumno.nombre} {persona_alumno.apellido}".strip(),
                "alumno_curso": nombre_curso,
                "tutor_nombre": nombre_tutor,
                "tutor_email": tutor_email,
                "tutor_telefono": tutor_tel,
                "monto_total": str(total),
                "monto_pagado": str(pagado),
                "saldo_pendiente": str(saldo),
                "conceptos_adeudados": conceptos,
                "estado": estado_cuota,
            })

        return Response(data)


class ReporteDesgloseFinancieroView(APIView):
    """Financial breakdown by service dimensions from issued quota snapshots (HU_M10)."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request):
        if request.auth.get("role") != "administrativo":
            return Response(
                {"detail": "Este reporte está disponible solo para el personal administrativo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        periodo = _periodo_reporte(request)
        if periodo is None:
            return Response(
                {"detail": "Parámetros inválidos. Use mes entre 1 y 12 y año desde 2000."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mes, anio = periodo
        cuotas = _cuotas_del_periodo(mes, anio).prefetch_related("pagos")
        return Response({
            "mes": mes,
            "anio": anio,
            **agrupar_reporte_financiero(cuotas),
        })


class FacturasReporteView(APIView):
    """Listado de facturas emitidas por rango de fechas para tutor y admin (HU_M08)."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request):
        role = request.auth.get("role")
        cuotas_qs = Cuota.objects.select_related(
            "id_legajo_alumno__id_persona",
            "id_legajo_alumno__id_curso__nivel_educativo",
            "id_tutor__id_persona",
        ).prefetch_related(
            "pagos",
            "comprobantes__pago",
        ).order_by("-fecha_vencimiento", "-id_cuota")

        if role == "padre":
            tutor = Tutor.objects.filter(id_persona__id_usuario=request.user).first()
            if tutor is None:
                return Response(
                    {"detail": "No se encontró el perfil de tutor asociado a la cuenta."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            legajos_hijos = TutorTutoraAlumno.objects.filter(id_tutor=tutor).values_list("id_alumno_id", flat=True)
            cuotas_qs = cuotas_qs.filter(id_tutor=tutor, id_legajo_alumno_id__in=legajos_hijos)
        elif role != "administrativo":
            return Response(
                {"detail": "Rol no autorizado para consultar reportes de facturas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        desde = request.query_params.get("desde")
        hasta = request.query_params.get("hasta")
        if desde:
            try:
                cuotas_qs = cuotas_qs.filter(fecha_vencimiento__gte=date.fromisoformat(desde.strip()))
            except ValueError:
                pass
        if hasta:
            try:
                cuotas_qs = cuotas_qs.filter(fecha_vencimiento__lte=date.fromisoformat(hasta.strip()))
            except ValueError:
                pass

        data = []
        hoy = timezone.localdate()
        for cuota in cuotas_qs:
            total = cuota.total_obligacion or Decimal("0")
            pagado = cuota.monto_pagado_actual()
            saldo = max(total - pagado, Decimal("0"))
            alumno = cuota.id_legajo_alumno
            persona_alumno = alumno.id_persona
            curso = alumno.id_curso
            nombre_curso = (
                f"{curso.anio}° {curso.comision} - {curso.nivel_educativo.nombre}"
                if curso and curso.nivel_educativo
                else ""
            )

            estado = (cuota.estado or "Pendiente").strip().casefold()
            if estado not in {"pagada", "parcial"} and cuota.fecha_vencimiento and cuota.fecha_vencimiento < hoy:
                estado = "vencida"

            comprobantes = []
            for comp in cuota.comprobantes.all():
                comprobantes.append({
                    "id": comp.id_comprobante,
                    "fecha_pago": comp.fecha_envio.date().isoformat() if comp.fecha_envio else hoy.isoformat(),
                    "importe": str(comp.pago.importe if comp.pago else pagado),
                    "estado": (comp.pago.estado if comp.pago else comp.estado).casefold(),
                    "archivo_url": comp.archivo.url if comp.archivo else None,
                })

            data.append({
                "id": cuota.id_cuota,
                "numero_factura": f"FAC-{cuota.periodo[:3].upper()}-{cuota.id_cuota:05d}",
                "fecha_emision": cuota.fecha_vencimiento.isoformat() if cuota.fecha_vencimiento else hoy.isoformat(),
                "periodo": cuota.periodo,
                "alumno_nombre": f"{persona_alumno.nombre} {persona_alumno.apellido}".strip(),
                "alumno_curso": nombre_curso,
                "monto_total": str(total),
                "monto_pagado": str(pagado),
                "saldo": str(saldo),
                "estado": estado,
                "comprobantes": comprobantes,
            })

        return Response(data)


class DeudaHistorialView(APIView):
    """Reporte de deuda acumulada discriminada por conceptos para el tutor (HU_M09)."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMobileAuthenticated]

    def get(self, request):
        if request.auth.get("role") != "padre":
            return Response(
                {"detail": "Este reporte está disponible solo para padres/tutores."},
                status=status.HTTP_403_FORBIDDEN,
            )

        tutor = Tutor.objects.filter(id_persona__id_usuario=request.user).first()
        if tutor is None:
            return Response(
                {"detail": "No se encontró el perfil de tutor asociado a la cuenta."},
                status=status.HTTP_403_FORBIDDEN,
            )

        legajos_hijos = TutorTutoraAlumno.objects.filter(id_tutor=tutor).values_list("id_alumno_id", flat=True)
        alumnos = (
            Alumno.objects.filter(legajo__in=legajos_hijos)
            .select_related("id_persona", "id_curso__nivel_educativo")
            .prefetch_related(
                "inscripciones_deportivas__id_grupo__id_disciplina",
                "inscripciones_transporte__id_recorrido",
                "inscripciones_comedor__id_servicio",
            )
            .order_by("id_persona__apellido", "id_persona__nombre")
        )

        desglose_alumnos = []
        total_deuda_general = Decimal("0")
        total_cuota_base_gral = Decimal("0")
        total_deportes_gral = Decimal("0")
        total_transporte_gral = Decimal("0")
        total_comedor_gral = Decimal("0")

        for alumno in alumnos:
            persona = alumno.id_persona
            curso = alumno.id_curso
            nombre_curso = (
                f"{curso.anio}° {curso.comision} - {curso.nivel_educativo.nombre}"
                if curso and curso.nivel_educativo
                else ""
            )

            cuotas_alumno = Cuota.objects.filter(
                id_tutor=tutor,
                id_legajo_alumno=alumno,
            ).prefetch_related("pagos")

            cuota_base_alumno = Decimal("0")
            deportes_alumno = Decimal("0")
            transporte_alumno = Decimal("0")
            comedor_alumno = Decimal("0")
            subtotal_alumno = Decimal("0")

            # Deportes activos
            monto_deportes_mensual = sum(
                (
                    d.id_grupo.id_disciplina.monto_mensual or Decimal("0")
                    for d in alumno.inscripciones_deportivas.all()
                    if (d.estado or "").casefold() == "activa"
                ),
                Decimal("0"),
            )
            # Transporte activo
            transp = next(
                (
                    t for t in alumno.inscripciones_transporte.all()
                    if (t.estado or "").casefold() == "activa"
                ),
                None,
            )
            monto_transporte_mensual = transp.id_recorrido.monto_mensual or Decimal("0") if transp else Decimal("0")
            # Comedor activo
            comed = next(
                (
                    c for c in alumno.inscripciones_comedor.all()
                    if (c.estado or "").casefold() == "activa"
                ),
                None,
            )
            monto_comedor_mensual = comed.id_servicio.monto_mensual or Decimal("0") if comed else Decimal("0")

            for c in cuotas_alumno:
                tot = c.total_obligacion or Decimal("0")
                pag = c.monto_pagado_actual()
                saldo = max(tot - pag, Decimal("0"))
                if saldo > Decimal("0"):
                    subtotal_alumno += saldo
                    # Asignación conceptual
                    base = c.monto or Decimal("0")
                    cuota_base_alumno += base
                    deportes_alumno += monto_deportes_mensual
                    transporte_alumno += monto_transporte_mensual
                    comedor_alumno += monto_comedor_mensual

            # Si hubo saldo pero la suma conceptual no coincide exactamente, calibrar a la cuota base
            suma_conceptos = cuota_base_alumno + deportes_alumno + transporte_alumno + comedor_alumno
            if subtotal_alumno > Decimal("0") and suma_conceptos != subtotal_alumno:
                cuota_base_alumno = max(subtotal_alumno - (deportes_alumno + transporte_alumno + comedor_alumno), Decimal("0"))

            desglose_alumnos.append({
                "alumno_legajo": alumno.legajo,
                "alumno_nombre": f"{persona.nombre} {persona.apellido}".strip(),
                "alumno_curso": nombre_curso,
                "cuota_base": str(cuota_base_alumno),
                "deportes": str(deportes_alumno),
                "transporte": str(transporte_alumno),
                "comedor": str(comedor_alumno),
                "subtotal_deuda": str(subtotal_alumno),
            })

            total_deuda_general += subtotal_alumno
            total_cuota_base_gral += cuota_base_alumno
            total_deportes_gral += deportes_alumno
            total_transporte_gral += transporte_alumno
            total_comedor_gral += comedor_alumno

        return Response({
            "tutor_id": tutor.id,
            "total_deuda": str(total_deuda_general),
            "deuda_cuota_base": str(total_cuota_base_gral),
            "deuda_deportes": str(total_deportes_gral),
            "deuda_transporte": str(total_transporte_gral),
            "deuda_comedor": str(total_comedor_gral),
            "desglose_alumnos": desglose_alumnos,
        })


