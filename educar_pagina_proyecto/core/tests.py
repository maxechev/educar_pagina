from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.test import Client, TestCase
from django.utils import timezone
from django.utils.crypto import get_random_string

from .models import (
    Alumno,
    Curso,
    DocumentacionAlumno,
    NivelEducativo,
    Persona,
    PersonalAdministrativo,
    PagoPendiente,
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
