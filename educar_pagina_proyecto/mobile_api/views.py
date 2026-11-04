from decimal import Decimal, InvalidOperation

from django.contrib.auth.hashers import check_password, make_password
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
    ComprobantePago,
    Cuota,
    PagoCuota,
    PagoPendiente,
    Persona,
    Tutor,
    TutorTutoraAlumno,
    Usuario,
)

from .authentication import MobileTokenAuthentication
from .models import MobileSession
from .services import mobile_role_for_user
from .tokens import TOKEN_TTL_SECONDS, create_access_token


class IsMobileAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, Usuario)


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

            if cuota.estado not in {"Pagada", "Parcial"} and cuota.fecha_vencimiento and cuota.fecha_vencimiento < timezone.localdate():
                cuota.estado = "Vencida"
            total = cuota.total_obligacion or Decimal("0")
            monto_pagado = cuota.monto_pagado_actual()
            saldo = max(total - monto_pagado, Decimal("0"))
            estado_cuota = (cuota.estado or "Pendiente").strip().casefold()
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
                    "comprobantes": [
                        {
                            "id": comprobante.id_comprobante,
                            "estado": comprobante.estado.casefold(),
                            "fecha_envio": comprobante.fecha_envio.isoformat(),
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

        legajos_hijos = TutorTutoraAlumno.objects.filter(id_tutor=tutor).values_list("id_alumno_id", flat=True)
        cuota = Cuota.objects.filter(
            id_cuota=cuota_id,
            id_tutor=tutor,
            id_legajo_alumno_id__in=legajos_hijos,
        ).first()
        if cuota is None:
            return Response({"detail": "La cuota no existe o no pertenece a un alumno asociado."}, status=status.HTTP_404_NOT_FOUND)

        saldo = max((cuota.total_obligacion or Decimal("0")) - cuota.monto_pagado_actual(), Decimal("0"))
        if importe > saldo:
            return Response({"detail": "El importe supera el saldo pendiente de la cuota.", "saldo": str(saldo)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
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
        if request.auth.get("role") != "padre":
            return Response({"detail": "Este recurso está disponible para padres/tutores."}, status=status.HTTP_403_FORBIDDEN)
        tutor = Tutor.objects.filter(id_persona__id_usuario=request.user).first()
        legajos_hijos = TutorTutoraAlumno.objects.filter(id_tutor=tutor).values_list("id_alumno_id", flat=True)
        comprobante = ComprobantePago.objects.filter(
            id_comprobante=comprobante_id,
            cuota__id_tutor=tutor,
            cuota__id_legajo_alumno_id__in=legajos_hijos,
        ).first()
        if comprobante is None or not comprobante.archivo:
            return Response({"detail": "Comprobante no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        try:
            archivo = comprobante.archivo.open("rb")
        except FileNotFoundError:
            return Response({"detail": "El archivo del comprobante no está disponible."}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(archivo, as_attachment=False, filename=comprobante.archivo.name.rsplit("/", 1)[-1])
