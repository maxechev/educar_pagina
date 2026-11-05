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
    Alumno,
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
        ).prefetch_related(
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
        return Response({**cuota, "discriminacion": None})


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


MESES_ESPANOL = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
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

        hoy = timezone.localdate()
        try:
            mes = int(request.query_params.get("mes", hoy.month))
            anio = int(request.query_params.get("anio", hoy.year))
        except (TypeError, ValueError):
            mes = hoy.month
            anio = hoy.year

        if not (1 <= mes <= 12):
            mes = hoy.month

        mes_nombre = MESES_ESPANOL[mes - 1]

        cuotas = Cuota.objects.filter(
            Q(periodo__icontains=mes_nombre) | Q(fecha_vencimiento__year=anio, fecha_vencimiento__month=mes)
        ).prefetch_related("pagos")

        total_facturado = sum((c.total_obligacion or Decimal("0") for c in cuotas), Decimal("0"))
        total_recaudado = sum((c.monto_pagado_actual() for c in cuotas), Decimal("0"))

        porcentaje = (
            round(float(total_recaudado / total_facturado * 100), 2)
            if total_facturado > 0
            else 0.0
        )

        ingresos_cuota_base = sum(
            (c.monto for c in cuotas if c.monto_pagado_actual() > 0),
            Decimal("0"),
        )
        ingresos_servicios = max(total_recaudado - ingresos_cuota_base, Decimal("0"))

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

        hoy = timezone.localdate()
        try:
            mes = int(request.query_params.get("mes", hoy.month))
            anio = int(request.query_params.get("anio", hoy.year))
        except (TypeError, ValueError):
            mes = hoy.month
            anio = hoy.year

        if not (1 <= mes <= 12):
            mes = hoy.month

        mes_nombre = MESES_ESPANOL[mes - 1]

        cuotas = (
            Cuota.objects.filter(
                Q(periodo__icontains=mes_nombre) | Q(fecha_vencimiento__year=anio, fecha_vencimiento__month=mes)
            )
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

        hoy = timezone.localdate()
        try:
            mes = int(request.query_params.get("mes", hoy.month))
            anio = int(request.query_params.get("anio", hoy.year))
        except (TypeError, ValueError):
            mes = hoy.month
            anio = hoy.year

        if not (1 <= mes <= 12):
            mes = hoy.month

        mes_nombre = MESES_ESPANOL[mes - 1]

        cuotas = (
            Cuota.objects.filter(
                Q(periodo__icontains=mes_nombre) | Q(fecha_vencimiento__year=anio, fecha_vencimiento__month=mes)
            )
            .select_related(
                "id_legajo_alumno__id_persona",
                "id_legajo_alumno__id_curso__nivel_educativo",
                "id_tutor__id_persona__id_usuario",
            )
            .prefetch_related(
                "pagos",
                "id_legajo_alumno__inscripciones_deportivas__id_grupo__id_disciplina",
                "id_legajo_alumno__inscripciones_transporte__id_recorrido",
                "id_legajo_alumno__inscripciones_comedor__id_servicio",
            )
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

            # Conceptos adeudados
            conceptos = ["Cuota Base"]
            for dep in alumno.inscripciones_deportivas.all():
                if (dep.estado or "").casefold() == "activa":
                    conceptos.append(dep.id_grupo.id_disciplina.nombre)
            for transp in alumno.inscripciones_transporte.all():
                if (transp.estado or "").casefold() == "activa":
                    conceptos.append(f"Transporte: {transp.id_recorrido.nombre}")
                    break
            for com in alumno.inscripciones_comedor.all():
                if (com.estado or "").casefold() == "activa":
                    conceptos.append("Comedor Escolar")
                    break

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

