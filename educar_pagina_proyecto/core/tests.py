from datetime import date

from django.contrib.auth.hashers import check_password, make_password
from django.test import Client, TestCase
from django.utils.crypto import get_random_string

from .models import Persona, PersonalAdministrativo, Tutor, Usuario
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
