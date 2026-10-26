from datetime import date

from django.contrib.auth.hashers import check_password, make_password
from django.test import Client, TestCase

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
        fachada = GestionEscolarFacade({'Usuario': Usuario})
        usuario = fachada.crear_usuario(
            'docente',
            nombre_usuario='docente_test',
            contrasenia='clave-segura',
        )

        self.assertNotEqual(usuario.contrasenia, 'clave-segura')
        self.assertTrue(check_password('clave-segura', usuario.contrasenia))

    def test_login_con_hash_redirige_al_dashboard_correcto(self):
        usuario = Usuario.objects.create(
            nombre_usuario='admin_test',
            contrasenia=make_password('clave-segura'),
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
            'password': 'clave-segura',
            'rol': 'administrativo',
        })

        self.assertRedirects(respuesta, '/administrativo/')

    def test_login_rechaza_clave_incorrecta(self):
        Usuario.objects.create(
            nombre_usuario='usuario_test',
            contrasenia=make_password('clave-correcta'),
            rol='administrativo',
            estado='Activo',
        )

        respuesta = self.client.post('/login/', {
            'usuario': 'usuario_test',
            'password': 'otra-clave',
            'rol': 'administrativo',
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Datos incorrectos')

    def test_padre_no_accede_al_dashboard_administrativo(self):
        usuario = Usuario.objects.create(
            nombre_usuario='padre_test',
            contrasenia=make_password('clave-segura'),
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
