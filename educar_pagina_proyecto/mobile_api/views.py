from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.models import Cuota, Persona, Tutor, TutorTutoraAlumno, Usuario

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
        ).order_by("-fecha_pago", "-id_cuota")

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
            cuotas = cuotas.filter(estado__iexact=estados_validos[estado_normalizado])

        data = []
        for cuota in cuotas:
            alumno = cuota.id_legajo_alumno
            persona = alumno.id_persona
            curso = alumno.id_curso
            nombre_curso = ""
            if curso:
                nivel = curso.nivel_educativo.nombre
                nombre_curso = f"{curso.anio}° Año {curso.comision} - {nivel}"

            estado_cuota = (cuota.estado or "").strip().casefold()
            monto_pagado = cuota.monto if estado_cuota == "pagada" else 0
            data.append(
                {
                    "id": cuota.id_cuota,
                    "periodo": cuota.periodo,
                    "monto": str(cuota.monto),
                    "monto_pagado": str(monto_pagado),
                    "fecha_pago": cuota.fecha_pago.isoformat(),
                    "estado": estado_cuota,
                    "alumno": {
                        "legajo": alumno.legajo,
                        "nombre_completo": f"{persona.nombre} {persona.apellido}".strip(),
                        "curso": nombre_curso,
                    },
                }
            )

        return Response(data)
