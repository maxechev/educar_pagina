from datetime import date
from decimal import Decimal
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.utils import timezone
from core.models import (
    Alumno,
    Cuota,
    PagoCuota,
    PagoPendiente,
    Persona,
    PersonalAdministrativo,
    Tutor,
    Usuario,
)
from mobile_api.tokens import create_access_token


class AdminComprobantesAPITestCase(TestCase):
    def setUp(self):
        # Admin user
        self.user_admin = Usuario.objects.create(
            nombre_usuario="admin_test",
            contrasenia=make_password("pass"),
            rol="administrativo",
            estado="Activo",
        )
        self.persona_admin = Persona.objects.create(
            id_usuario=self.user_admin,
            nombre="Admin",
            apellido="General",
            dni=11111111,
            fecha_nacimiento=date(1980, 1, 1),
        )
        self.personal_admin = PersonalAdministrativo.objects.create(
            id_persona=self.persona_admin,
            sector="Administración",
            cargo="Administrador",
            fecha_ingreso=date(2020, 1, 1),
        )
        self.token_admin = create_access_token(self.user_admin.pk, "administrativo")

        # Tutor & Alumno
        self.user_tutor = Usuario.objects.create(
            nombre_usuario="tutor_test",
            contrasenia=make_password("pass"),
            rol="padre",
            estado="Activo",
        )
        self.persona_tutor = Persona.objects.create(
            id_usuario=self.user_tutor,
            nombre="Carlos",
            apellido="Tutor",
            dni=22222222,
            fecha_nacimiento=date(1985, 1, 1),
        )
        self.tutor = Tutor.objects.create(id_persona=self.persona_tutor)
        self.token_tutor = create_access_token(self.user_tutor.pk, "padre")

        self.persona_alumno = Persona.objects.create(
            nombre="Lucas",
            apellido="Alumno",
            dni=33333333,
            fecha_nacimiento=date(2010, 1, 1),
        )
        self.alumno = Alumno.objects.create(id_persona=self.persona_alumno, legajo=9999)

        self.cuota = Cuota.objects.create(
            periodo="Noviembre 2026",
            monto=Decimal("40000.00"),
            monto_total=Decimal("40000.00"),
            id_tutor=self.tutor,
            id_legajo_alumno=self.alumno,
            estado="Pendiente",
        )

        self.pago_pendiente = PagoPendiente.objects.create(
            id_tutor=self.tutor,
            legajo_alumno=self.alumno,
            mes="Noviembre 2026",
            importe=Decimal("40000.00"),
            estado="En revisión",
            fecha_solicitud=timezone.now(),
        )

        self.pago_cuota = PagoCuota.objects.create(
            cuota=self.cuota,
            solicitud=self.pago_pendiente,
            tutor=self.tutor,
            importe=Decimal("40000.00"),
            estado="En revisión",
        )

    def test_listar_pendientes_requiere_rol_administrativo(self):
        # Tutor role fails
        res = self.client.get(
            "/api/comprobantes/pendientes/",
            HTTP_AUTHORIZATION=f"Bearer {self.token_tutor}",
        )
        self.assertEqual(res.status_code, 403)

        # Admin role succeeds
        res_admin = self.client.get(
            "/api/comprobantes/pendientes/",
            HTTP_AUTHORIZATION=f"Bearer {self.token_admin}",
        )
        self.assertEqual(res_admin.status_code, 200)
        data = res_admin.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.pago_pendiente.id_pago)
        self.assertEqual(data[0]["importe"], "40000.00")
        self.assertEqual(data[0]["alumno"]["legajo"], 9999)

    def test_aprobar_pago_admin(self):
        res = self.client.post(
            f"/api/comprobantes/{self.pago_pendiente.id_pago}/aprobar/",
            HTTP_AUTHORIZATION=f"Bearer {self.token_admin}",
        )
        self.assertEqual(res.status_code, 200)
        self.pago_pendiente.refresh_from_db()
        self.assertEqual(self.pago_pendiente.estado, "Pagado")

        self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.estado, "Pagada")

    def test_rechazar_pago_admin(self):
        # Without reason fails
        res_fail = self.client.post(
            f"/api/comprobantes/{self.pago_pendiente.id_pago}/rechazar/",
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token_admin}",
        )
        self.assertEqual(res_fail.status_code, 400)

        # With reason succeeds
        res = self.client.post(
            f"/api/comprobantes/{self.pago_pendiente.id_pago}/rechazar/",
            data={"motivo": "Comprobante ilegible"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token_admin}",
        )
        self.assertEqual(res.status_code, 200)
        self.pago_pendiente.refresh_from_db()
        self.assertEqual(self.pago_pendiente.estado, "Rechazado")
        self.assertEqual(self.pago_pendiente.motivo_rechazo, "Comprobante ilegible")
