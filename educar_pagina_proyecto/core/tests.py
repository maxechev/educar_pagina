from datetime import date, time
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.test import Client, TestCase
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from .models import (
    Alumno,
    Curso,
    DocumentacionAlumno,
    NivelEducativo,
    InscripcionTransporte,
    InscripcionComedor,
    InscripcionDeportiva,
    RecorridoTransporte,
    ServicioComedor,
    DisciplinaDeportiva,
    GrupoDeportivo,
    Instalacion,
    Docente,
    Persona,
    PersonalAdministrativo,
    PagoPendiente,
    PagoCuota,
    ComprobantePago,
    Cuota,
    Tutor,
    TutorTutoraAlumno,
    Usuario,
)
from .patterns import GestionEscolarFacade


class SeguridadYPatronesTests(TestCase):
    def setUp(self):
        self.client = Client()

    def crear_persona(self, usuario, dni='99000001', nombre='Prueba', apellido='Usuario'):
        return Persona.objects.create(
            id_usuario=usuario,
            dni=dni,
            nombre=nombre,
            apellido=apellido,
            fecha_nacimiento=date(1990, 1, 1),
        )

    def test_factory_almacena_hash_y_no_texto_plano(self):
        password_prueba = get_random_string(32)
        fachada = GestionEscolarFacade({'Usuario': Usuario})
        usuario = fachada.crear_usuario(
            'docente',
            nombre_usuario='docente_test',
            contrasenia=password_prueba,
        )

        self.assertNotEqual(usuario.contrasenia, password_prueba)
        self.assertTrue(check_password(password_prueba, usuario.contrasenia))

    def test_login_con_hash_redirige_al_dashboard_correcto(self):
        password_prueba = get_random_string(32)
        usuario = Usuario.objects.create(
            nombre_usuario='admin_test',
            contrasenia=make_password(password_prueba),
            rol='administrativo',
            estado='Activo',
        )
        persona = self.crear_persona(usuario)
        PersonalAdministrativo.objects.create(
            id_persona=persona,
            sector='Administración',
            cargo='Administrador',
            fecha_ingreso=date.today(),
        )

        respuesta = self.client.post('/login/', {
            'usuario': 'admin_test',
            'password': password_prueba,
            'rol': 'administrativo',
        })

        self.assertRedirects(respuesta, '/administrativo/')

    def test_login_rechaza_clave_incorrecta(self):
        password_correcta = get_random_string(32)
        password_incorrecta = get_random_string(32)
        Usuario.objects.create(
            nombre_usuario='usuario_test',
            contrasenia=make_password(password_correcta),
            rol='administrativo',
            estado='Activo',
        )

        respuesta = self.client.post('/login/', {
            'usuario': 'usuario_test',
            'password': password_incorrecta,
            'rol': 'administrativo',
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Datos incorrectos')

    def test_padre_no_accede_al_dashboard_administrativo(self):
        password_prueba = get_random_string(32)
        usuario = Usuario.objects.create(
            nombre_usuario='padre_test',
            contrasenia=make_password(password_prueba),
            rol='padre',
            estado='Activo',
        )
        persona = self.crear_persona(usuario, dni='99000002')
        Tutor.objects.create(id_persona=persona)
        session = self.client.session
        session['usuario_id'] = usuario.id
        session.save()

        respuesta = self.client.get('/administrativo/')

        self.assertRedirects(respuesta, '/padres/')

    def test_login_rota_la_clave_de_sesion(self):
        password_prueba = get_random_string(32)
        usuario = Usuario.objects.create(
            nombre_usuario='admin_rotacion',
            contrasenia=make_password(password_prueba),
            rol='administrativo',
            estado='Activo',
        )
        persona = self.crear_persona(usuario, dni='99000003')
        PersonalAdministrativo.objects.create(
            id_persona=persona,
            sector='Administración',
            cargo='Administrador',
            fecha_ingreso=date.today(),
        )
        session = self.client.session
        session['dato_anonimo'] = 'no conservar'
        session.save()
        clave_anterior = session.session_key

        respuesta = self.client.post('/login/', {
            'usuario': 'admin_rotacion',
            'password': password_prueba,
            'rol': 'administrativo',
        })

        self.assertRedirects(respuesta, '/administrativo/')
        self.assertNotEqual(self.client.session.session_key, clave_anterior)
        self.assertNotIn('dato_anonimo', self.client.session)

    def test_acciones_sensibles_rechazan_get(self):
        urls = (
            '/aprobar-inscripcion/1/',
            '/rechazar-inscripcion/1/',
            '/aprobar-pago/1/',
            '/rechazar-pago/1/',
            '/aprobar-documentacion/1/',
            '/rechazar-documentacion/1/',
            '/administrativo/alumnos/1/baja/',
            '/administrativo/usuarios/1/baja/',
            '/docente/tareas/1/borrar/',
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_operaciones_administrativas_rechazan_sesion_ajena(self):
        urls = (
            '/aprobar-inscripcion/999/',
            '/aprobar-pago/999/',
            '/aprobar-documentacion/999/',
            '/administrativo/alumnos/alta/',
        )
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.post(url)
                self.assertRedirects(respuesta, '/login/')

    def test_tutor_no_puede_registrar_pago_para_alumno_ajeno(self):
        usuario = Usuario.objects.create(
            nombre_usuario='tutor_ajeno',
            contrasenia=make_password(get_random_string(32)),
            rol='padre',
            estado='Activo',
        )
        persona_tutor = self.crear_persona(
            usuario, dni='99000004', nombre='Tutor', apellido='Prueba'
        )
        tutor = Tutor.objects.create(id_persona=persona_tutor)

        persona_alumno = Persona.objects.create(
            dni='99000005',
            nombre='Alumno',
            apellido='Ajeno',
            fecha_nacimiento=date(2015, 1, 1),
        )
        nivel = NivelEducativo.objects.create(nombre='Nivel test seguridad')
        curso = Curso.objects.create(
            comision='A', anio=4, turno='Mañana', nivel_educativo=nivel
        )
        alumno = Alumno.objects.create(
            id_persona=persona_alumno,
            fecha_ingreso=date.today(),
            id_curso=curso,
        )
        # Existe una relación con otro tutor, no con la cuenta de esta prueba.
        otro_tutor_persona = Persona.objects.create(
            dni='99000006',
            nombre='Otro',
            apellido='Tutor',
            fecha_nacimiento=date(1980, 1, 1),
        )
        otro_tutor = Tutor.objects.create(id_persona=otro_tutor_persona)
        TutorTutoraAlumno.objects.create(
            id_tutor=otro_tutor,
            id_alumno=alumno,
            tipo_parentesco='Madre',
        )
        session = self.client.session
        session['usuario_id'] = usuario.id
        session.save()

        respuesta = self.client.post('/registrar-pago/', {
            'alumno': alumno.legajo,
            'mes': 'Octubre',
        })

        self.assertRedirects(respuesta, '/padres/')
        self.assertEqual(PagoPendiente.objects.count(), 0)

        respuesta = self.client.post('/enviar-documentacion/', {
            'alumno': alumno.legajo,
        })
        self.assertRedirects(respuesta, '/padres/')
        self.assertFalse(DocumentacionAlumno.objects.exists())

        documentacion = DocumentacionAlumno.objects.create(
            legajo_alumno=alumno,
            dni_frente='documentacion/privado.jpg',
            fecha_envio=timezone.now(),
        )
        self.assertEqual(
            self.client.get('/media/documentacion/privado.jpg').status_code,
            404,
        )
        url_documento = (
            f'/documentacion/{documentacion.id_documentacion}/dni_frente/'
        )
        respuesta = self.client.get(url_documento)
        self.assertEqual(respuesta.status_code, 404)

        TutorTutoraAlumno.objects.create(
            id_tutor=tutor,
            id_alumno=alumno,
            tipo_parentesco='Padre',
        )
        with (
            patch.object(Path, 'is_file', return_value=True),
            patch.object(Path, 'open', return_value=BytesIO(b'contenido privado')),
        ):
            respuesta = self.client.get(url_documento)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            b''.join(respuesta.streaming_content), b'contenido privado'
        )


class FlujoPagosTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.api_client = APIClient()
        self.admin_usuario = Usuario.objects.create(
            nombre_usuario='admin_pagos',
            contrasenia=make_password('pass1234'),
            rol='administrativo',
            estado='Activo',
        )
        admin_persona = Persona.objects.create(
            id_usuario=self.admin_usuario,
            dni='99100001', nombre='Admin', apellido='Pagos',
            fecha_nacimiento=date(1980, 1, 1),
        )
        PersonalAdministrativo.objects.create(
            id_persona=admin_persona,
            sector='Administración', cargo='Administrador',
            fecha_ingreso=date.today(),
        )
        tutor_usuario = Usuario.objects.create(
            nombre_usuario='tutor_pagos',
            contrasenia=make_password('pass1234'),
            rol='padre', estado='Activo',
        )
        self.tutor_usuario = tutor_usuario
        tutor_persona = Persona.objects.create(
            id_usuario=tutor_usuario,
            dni='99100002', nombre='Tutor', apellido='Pagos',
            fecha_nacimiento=date(1980, 1, 1),
        )
        self.tutor = Tutor.objects.create(id_persona=tutor_persona)
        alumno_persona = Persona.objects.create(
            dni='99100003', nombre='Alumno', apellido='Pago',
            fecha_nacimiento=date(2015, 1, 1),
        )
        nivel = NivelEducativo.objects.create(nombre='Nivel pagos')
        curso = Curso.objects.create(
            comision='A', anio=4, turno='Mañana', nivel_educativo=nivel,
        )
        self.alumno = Alumno.objects.create(
            id_persona=alumno_persona,
            fecha_ingreso=date.today(), id_curso=curso,
        )
        TutorTutoraAlumno.objects.create(id_tutor=self.tutor, id_alumno=self.alumno)
        self.cuota = Cuota.objects.create(
            periodo='Noviembre', monto=1000, monto_total=1000,
            estado='Pendiente', id_tutor=self.tutor,
            id_legajo_alumno=self.alumno,
        )

        session = self.client.session
        session['usuario_id'] = self.admin_usuario.id
        session.save()

    def _crear_solicitud(self, importe=1000):
        return PagoPendiente.objects.create(
            id_tutor=self.tutor, legajo_alumno=self.alumno,
            mes='Noviembre', importe=importe, estado='En revisión',
            fecha_solicitud=timezone.now(),
        )

    def test_aprobar_pago_es_idempotente_y_conserva_historial(self):
        solicitud = self._crear_solicitud()

        primera = self.client.post(f'/aprobar-pago/{solicitud.id_pago}/')
        segunda = self.client.post(f'/aprobar-pago/{solicitud.id_pago}/')

        self.assertEqual(primera.status_code, 302)
        self.assertEqual(segunda.status_code, 302)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'Pagado')
        self.assertEqual(PagoCuota.objects.filter(solicitud=solicitud).count(), 1)
        self.assertEqual(PagoCuota.objects.get(solicitud=solicitud).estado, 'Pagado')

    def test_rechazo_exige_motivo_y_conserva_solicitud(self):
        solicitud = self._crear_solicitud()

        sin_motivo = self.client.post(f'/rechazar-pago/{solicitud.id_pago}/')
        solicitud.refresh_from_db()
        self.assertEqual(sin_motivo.status_code, 302)
        self.assertEqual(solicitud.estado, 'En revisión')

        respuesta = self.client.post(
            f'/rechazar-pago/{solicitud.id_pago}/',
            {'motivo_rechazo': 'El comprobante no es legible.'},
        )
        solicitud.refresh_from_db()
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(solicitud.estado, 'Rechazado')
        self.assertEqual(solicitud.motivo_rechazo, 'El comprobante no es legible.')

    def test_usuario_sin_rol_administrativo_no_puede_aprobar(self):
        solicitud = self._crear_solicitud()
        session = self.client.session
        session['usuario_id'] = self.tutor.id_persona.id_usuario_id
        session.save()

        respuesta = self.client.post(f'/aprobar-pago/{solicitud.id_pago}/')
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], '/login/')
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'En revisión')

    def test_comprobante_de_tutor_pasa_a_en_revision(self):
        from mobile_api.tokens import create_access_token

        token = create_access_token(self.tutor_usuario.id, 'padre')
        respuesta = self.api_client.post(
            '/api/comprobantes/',
            {
                'cuota_id': self.cuota.id_cuota,
                'importe': '250',
                'archivo': SimpleUploadedFile(
                    'comprobante.txt', b'comprobante de prueba', content_type='text/plain'
                ),
            },
            format='multipart',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(respuesta.status_code, 201)
        solicitud = PagoPendiente.objects.get(id_tutor=self.tutor)
        self.assertEqual(solicitud.estado, 'En revisión')
        self.assertEqual(PagoCuota.objects.get(solicitud=solicitud).estado, 'En revisión')
        self.assertTrue(ComprobantePago.objects.filter(cuota=self.cuota).exists())

    def test_detalle_cuota_reutiliza_datos_y_respeta_alumnos_asociados(self):
        from mobile_api.tokens import create_access_token

        token = create_access_token(self.tutor_usuario.id, 'padre')
        respuesta = self.api_client.get(
            f'/api/cuotas/{self.cuota.id_cuota}/',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['id'], self.cuota.id_cuota)
        self.assertIsNone(respuesta.data['discriminacion'])
        self.assertEqual(respuesta.data['estado'], 'pendiente')

        otra_persona = Persona.objects.create(
            dni='99100004', nombre='Ajeno', apellido='Pago',
            fecha_nacimiento=date(2015, 1, 1),
        )
        otro_alumno = Alumno.objects.create(
            id_persona=otra_persona, fecha_ingreso=date.today(),
            id_curso=self.alumno.id_curso,
        )
        otra_cuota = Cuota.objects.create(
            periodo='Noviembre', monto=1000, monto_total=1000,
            estado='Pendiente', id_tutor=self.tutor,
            id_legajo_alumno=otro_alumno,
        )
        no_autorizada = self.api_client.get(
            f'/api/cuotas/{otra_cuota.id_cuota}/',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(no_autorizada.status_code, 404)

    def test_servicios_inscripciones_solo_incluye_hijos_del_tutor(self):
        from mobile_api.tokens import create_access_token

        recorrido = RecorridoTransporte.objects.create(
            nombre='Recorrido API test', estado='Activo',
        )
        InscripcionTransporte.objects.create(
            id_alumno=self.alumno, id_recorrido=recorrido, estado='Activa',
        )
        comedor = ServicioComedor.objects.create(nombre='Comedor API test', estado='Activo')
        InscripcionComedor.objects.create(
            id_alumno=self.alumno, id_servicio=comedor, estado='Activa',
        )
        instalacion = Instalacion.objects.create(
            nombre='Instalación API test', capacidad=30, estado='Activo',
        )
        deporte = DisciplinaDeportiva.objects.create(
            nombre='Deporte API test', id_instalacion=instalacion,
        )
        docente_persona = Persona.objects.create(
            dni='99100005', nombre='Docente', apellido='Test',
            fecha_nacimiento=date(1980, 1, 1),
        )
        docente = Docente.objects.create(
            id_persona=docente_persona, titulo='Profesor de deporte',
        )
        grupo = GrupoDeportivo.objects.create(
            id_disciplina=deporte,
            nivel_educativo=self.alumno.id_curso.nivel_educativo,
            profesor_responsable=docente,
            dia_semana='lunes',
            hora_inicio=time(16, 0),
            hora_fin=time(18, 0),
            estado='Activo',
        )
        InscripcionDeportiva.objects.create(
            id_alumno=self.alumno, id_grupo=grupo, estado='Activa',
        )
        ajeno_persona = Persona.objects.create(
            dni='99100004', nombre='Ajeno', apellido='Pago',
            fecha_nacimiento=date(2015, 1, 1),
        )
        ajeno = Alumno.objects.create(
            id_persona=ajeno_persona, fecha_ingreso=date.today(),
            id_curso=self.alumno.id_curso,
        )
        InscripcionTransporte.objects.create(
            id_alumno=ajeno, id_recorrido=recorrido, estado='Activa',
        )

        token = create_access_token(self.tutor_usuario.id, 'padre')
        respuesta = self.api_client.get(
            '/api/servicios/inscripciones/',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.data), 1)
        self.assertEqual(respuesta.data[0]['alumno']['legajo'], self.alumno.legajo)
        self.assertEqual(respuesta.data[0]['transporte']['recorrido'], recorrido.nombre)
        self.assertEqual(respuesta.data[0]['transporte']['monto_mensual'], '10000.00')
        self.assertEqual(respuesta.data[0]['deportes'][0]['monto_mensual'], '5000.00')
        self.assertEqual(respuesta.data[0]['comedor']['monto_mensual'], '5000.00')
