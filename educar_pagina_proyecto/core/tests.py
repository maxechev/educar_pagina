from datetime import date, time
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core import mail
from rest_framework.test import APIClient

from .models import (
    Alumno,
    Arancel,
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
from .factura_pdf import generar_factura_pdf


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

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='notificaciones@test.com',
    )
    def test_aprobacion_envia_un_unico_correo_con_saldo_restante(self):
        self.tutor_usuario.correo = 'tutor.pagos@test.com'
        self.tutor_usuario.save(update_fields=['correo'])
        solicitud = self._crear_solicitud(importe=250)
        self.cuota.conceptos = [
            {
                'clave': 'cuota_base',
                'concepto': 'Cuota base (Nivel pagos)',
                'tipo': 'cuota_base',
                'monto': '700.00',
            },
            {
                'clave': 'deporte:1',
                'concepto': 'Deporte: Vóley',
                'tipo': 'deporte',
                'monto': '300.00',
            },
        ]
        self.cuota.save(update_fields=['conceptos'])
        PagoCuota.objects.create(
            cuota=self.cuota,
            solicitud=solicitud,
            tutor=self.tutor,
            importe=250,
            medio_pago='Transferencia',
            conceptos_aplicados={'deporte:1': '250.00'},
            estado='En revisión',
        )
        mail.outbox.clear()

        with patch('core.views.generar_factura_pdf', wraps=generar_factura_pdf) as generar_pdf:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(f'/aprobar-pago/{solicitud.id_pago}/')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            generar_pdf.call_args.kwargs['desglose_conceptos'],
            [{'concepto': 'Deporte: Vóley', 'monto': '250.00'}],
        )
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ['tutor.pagos@test.com'])
        self.assertEqual(correo.from_email, 'notificaciones@test.com')
        self.assertIn('Pago aprobado', correo.subject)
        self.assertIn('Saldo restante: 750', correo.body)
        self.assertIn('comprobante PDF', correo.body)
        self.assertEqual(len(correo.attachments), 1)
        nombre_archivo, contenido_pdf, tipo_contenido = correo.attachments[0]
        pago_aprobado = PagoCuota.objects.get(solicitud=solicitud)
        self.assertEqual(nombre_archivo, f'comprobante_pago_{pago_aprobado.id_pago}.pdf')
        self.assertEqual(tipo_contenido, 'application/pdf')
        self.assertTrue(contenido_pdf.startswith(b'%PDF-'))
        self.assertGreater(len(contenido_pdf), 1000)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f'/aprobar-pago/{solicitud.id_pago}/')
        self.assertEqual(len(mail.outbox), 1)

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

    def test_comprobante_puede_pagar_conceptos_completos_seleccionados(self):
        from mobile_api.tokens import create_access_token

        self.cuota.conceptos = [
            {'clave': 'cuota_base', 'tipo': 'cuota_base', 'concepto': 'Cuota base', 'monto': '700.00'},
            {'clave': 'transporte:1', 'tipo': 'transporte', 'concepto': 'Transporte: Norte', 'monto': '300.00'},
        ]
        self.cuota.save(update_fields=['conceptos'])
        token = create_access_token(self.tutor_usuario.id, 'padre')
        cuotas_response = self.api_client.get(
            '/api/cuotas/', HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(cuotas_response.status_code, 200)
        cuota_api = next(
            item for item in cuotas_response.data
            if item['id'] == self.cuota.id_cuota
        )
        self.assertEqual(
            [item['clave'] for item in cuota_api['conceptos_pago']],
            ['cuota_base', 'transporte:1'],
        )
        self.assertEqual(
            [item['saldo_disponible'] for item in cuota_api['conceptos_pago']],
            ['700.00', '300.00'],
        )
        datos = {
            'cuota_id': self.cuota.id_cuota,
            'importe': '700.00',
            'conceptos_seleccionados': '["cuota_base"]',
            'archivo': SimpleUploadedFile('comprobante.pdf', b'%PDF-prueba', content_type='application/pdf'),
        }
        respuesta = self.api_client.post(
            '/api/comprobantes/', datos, format='multipart',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(respuesta.status_code, 201)
        pago = PagoCuota.objects.get(id_pago=respuesta.data['pago_id'])
        self.assertEqual(pago.conceptos_aplicados, {'cuota_base': '700.00'})
        cuotas_actualizadas = self.api_client.get(
            '/api/cuotas/', HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        cuota_actualizada = next(
            item for item in cuotas_actualizadas.data
            if item['id'] == self.cuota.id_cuota
        )
        self.assertEqual(
            [item['saldo_disponible'] for item in cuota_actualizada['conceptos_pago']],
            ['0.00', '300.00'],
        )

        duplicado = self.api_client.post(
            '/api/comprobantes/',
            {
                'cuota_id': self.cuota.id_cuota,
                'importe': '700.00',
                'conceptos_seleccionados': '["cuota_base"]',
                'archivo': SimpleUploadedFile('otro.pdf', b'%PDF-prueba', content_type='application/pdf'),
            },
            format='multipart',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(duplicado.status_code, 400)

        importe_incompleto = self.api_client.post(
            '/api/comprobantes/',
            {
                'cuota_id': self.cuota.id_cuota,
                'importe': '500.00',
                'conceptos_seleccionados': '["transporte:1"]',
                'archivo': SimpleUploadedFile('parcial.pdf', b'%PDF-prueba', content_type='application/pdf'),
            },
            format='multipart',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(importe_incompleto.status_code, 400)

    def test_cuota_historica_bloquea_el_saldo_mientras_hay_comprobante_en_revision(self):
        from mobile_api.tokens import create_access_token

        token = create_access_token(self.tutor_usuario.id, 'padre')
        datos = {
            'cuota_id': self.cuota.id_cuota,
            'importe': '1000.00',
            'conceptos_seleccionados': '["__saldo_total__"]',
            'archivo': SimpleUploadedFile('historico.pdf', b'%PDF-prueba', content_type='application/pdf'),
        }
        primera = self.api_client.post(
            '/api/comprobantes/', datos, format='multipart',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(primera.status_code, 201)

        cuotas = self.api_client.get('/api/cuotas/', HTTP_AUTHORIZATION=f'Bearer {token}')
        cuota_api = next(item for item in cuotas.data if item['id'] == self.cuota.id_cuota)
        self.assertEqual(cuota_api['conceptos_pago'][0]['saldo_disponible'], '0.00')

        repetido = self.api_client.post(
            '/api/comprobantes/',
            {
                **datos,
                'archivo': SimpleUploadedFile('historico-otro.pdf', b'%PDF-prueba', content_type='application/pdf'),
            },
            format='multipart',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(repetido.status_code, 400)

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


class ComandosYReportesTests(TestCase):
    def setUp(self):
        self.api_client = APIClient()

        # Admin user
        self.admin_usuario = Usuario.objects.create(
            nombre_usuario='admin_reportes',
            contrasenia=make_password('pass1234'),
            rol='administrativo',
            estado='Activo',
            correo='admin@colegio.edu.ar',
        )
        admin_persona = Persona.objects.create(
            id_usuario=self.admin_usuario,
            dni='99200001',
            nombre='Santiago',
            apellido='Administrador',
            fecha_nacimiento=date(1985, 5, 10),
        )
        PersonalAdministrativo.objects.create(
            id_persona=admin_persona,
            sector='Administración',
            cargo='Administrador',
            fecha_ingreso=date.today(),
        )

        # Tutor 1 (con deuda)
        self.tutor_usuario = Usuario.objects.create(
            nombre_usuario='tutor_deudor',
            contrasenia=make_password('pass1234'),
            rol='padre',
            estado='Activo',
            correo='tutor.deuda@test.com',
        )
        tutor_persona = Persona.objects.create(
            id_usuario=self.tutor_usuario,
            dni='99200002',
            nombre='Carlos',
            apellido='Gómez',
            fecha_nacimiento=date(1980, 3, 15),
        )
        self.tutor = Tutor.objects.create(id_persona=tutor_persona, email_contacto='tutor.deuda@test.com')

        # Nivel y Curso
        self.nivel, _ = NivelEducativo.objects.get_or_create(
            nombre='Nivel Primario Test',
            defaults={'estado': 'Activo'}
        )
        self.arancel, _ = Arancel.objects.get_or_create(
            nivel='Nivel Primario Test',
            defaults={'monto': 25000}
        )
        self.curso = Curso.objects.create(
            comision='A',
            anio=5,
            turno='Mañana',
            nivel_educativo=self.nivel,
        )

        # Alumno 1
        alumno_persona = Persona.objects.create(
            dni='99200003',
            nombre='Lucas',
            apellido='Gómez',
            fecha_nacimiento=date(2014, 8, 20),
        )
        self.alumno = Alumno.objects.create(
            id_persona=alumno_persona,
            fecha_ingreso=date.today(),
            id_curso=self.curso,
            estado='Activo',
        )
        TutorTutoraAlumno.objects.create(id_tutor=self.tutor, id_alumno=self.alumno)

        # Servicios extracurriculares
        self.recorrido = RecorridoTransporte.objects.create(
            nombre='Recorrido Norte Test', monto_mensual=8000, estado='Activo'
        )
        InscripcionTransporte.objects.create(
            id_alumno=self.alumno, id_recorrido=self.recorrido, estado='Activa'
        )

        self.comedor = ServicioComedor.objects.create(
            nombre='Comedor Test', monto_mensual=5000, estado='Activo'
        )
        InscripcionComedor.objects.create(
            id_alumno=self.alumno, id_servicio=self.comedor, estado='Activa'
        )

        docente_persona = Persona.objects.create(
            dni='99200004', nombre='Profesor', apellido='Deportes', fecha_nacimiento=date(1985, 1, 1)
        )
        docente = Docente.objects.create(id_persona=docente_persona)
        instalacion = Instalacion.objects.create(nombre='Gimnasio Test', capacidad=50, estado='Activo')
        disciplina = DisciplinaDeportiva.objects.create(
            nombre='Básquet Test', id_instalacion=instalacion, monto_mensual=4000
        )
        grupo = GrupoDeportivo.objects.create(
            id_disciplina=disciplina,
            nivel_educativo=self.nivel,
            profesor_responsable=docente,
            dia_semana='Martes',
            hora_inicio=time(17, 0),
            hora_fin=time(18, 30),
            estado='Activo',
        )
        InscripcionDeportiva.objects.create(
            id_alumno=self.alumno, id_grupo=grupo, estado='Activa'
        )

        from mobile_api.tokens import create_access_token
        self.admin_token = create_access_token(self.admin_usuario.id, 'administrativo')
        self.tutor_token = create_access_token(self.tutor_usuario.id, 'padre')

    def test_emitir_facturas_mes_calcula_servicios_genera_pdf_y_envia_correo(self):
        mail.outbox.clear()
        call_command('emitir_facturas_mes', mes=11, anio=2026)

        cuota = Cuota.objects.get(id_legajo_alumno=self.alumno, periodo='Noviembre 2026')
        # Base: 25000 + Transporte: 8000 + Comedor: 5000 + Básquet: 4000 = 42000
        self.assertEqual(cuota.monto, 25000)
        self.assertEqual(cuota.total_obligacion, 42000)
        self.assertEqual(cuota.estado, 'Pendiente')

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('Noviembre 2026', email.subject)
        self.assertIn('Lucas Gómez', email.subject)
        self.assertEqual(email.to, ['tutor.deuda@test.com'])
        self.assertEqual(len(email.attachments), 1)
        self.assertTrue(email.attachments[0][0].endswith('.pdf'))

    def test_emitir_facturas_mes_dry_run_no_modifica_db(self):
        mail.outbox.clear()
        call_command('emitir_facturas_mes', mes=12, anio=2026, dry_run=True)

        self.assertFalse(Cuota.objects.filter(periodo='Diciembre 2026').exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_emitir_facturas_mes_filtra_por_legajo_en_dry_run(self):
        otro_persona = Persona.objects.create(
            dni='99200999', nombre='Otro', apellido='Alumno', fecha_nacimiento=date(2015, 1, 1)
        )
        otro_alumno = Alumno.objects.create(
            legajo=99200999, id_persona=otro_persona, id_curso=self.curso, estado='Activo'
        )
        TutorTutoraAlumno.objects.create(id_tutor=self.tutor, id_alumno=otro_alumno)

        call_command(
            'emitir_facturas_mes', mes=12, anio=2026, dry_run=True, legajo=self.alumno.legajo
        )

        self.assertFalse(Cuota.objects.filter(periodo='Diciembre 2026').exists())

    def test_enviar_factura_existente_no_modifica_cuota_y_adjunta_pdf(self):
        cuota = Cuota.objects.create(
            periodo='Noviembre 2026', monto=25000, monto_total=42000,
            estado='Pendiente', id_tutor=self.tutor, id_legajo_alumno=self.alumno,
        )
        valores_antes = (cuota.monto, cuota.monto_total, cuota.estado)
        mail.outbox.clear()

        call_command(
            'enviar_factura_existente', cuota_id=cuota.id_cuota,
            legajo=self.alumno.legajo, destinatario='prueba@ejemplo.com',
        )

        cuota.refresh_from_db()
        self.assertEqual((cuota.monto, cuota.monto_total, cuota.estado), valores_antes)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['prueba@ejemplo.com'])
        self.assertEqual(mail.outbox[0].attachments[0][2], 'application/pdf')

    def test_enviar_factura_existente_rechaza_cuota_de_otro_legajo(self):
        cuota = Cuota.objects.create(
            periodo='Noviembre 2026', monto=25000, monto_total=25000,
            estado='Pendiente', id_tutor=self.tutor, id_legajo_alumno=self.alumno,
        )
        mail.outbox.clear()

        with self.assertRaises(CommandError):
            call_command(
                'enviar_factura_existente', cuota_id=cuota.id_cuota,
                legajo=99200999, destinatario='prueba@ejemplo.com',
            )

        self.assertEqual(len(mail.outbox), 0)

    def test_enviar_recordatorios_deuda_solo_a_morosos(self):
        # Crear cuota adeudada para tutor 1
        Cuota.objects.create(
            periodo='Noviembre 2026',
            monto=25000,
            monto_total=42000,
            estado='Pendiente',
            fecha_vencimiento=date(2026, 11, 10),
            id_tutor=self.tutor,
            id_legajo_alumno=self.alumno,
        )

        mail.outbox.clear()
        call_command('enviar_recordatorios_deuda', periodo='Noviembre 2026')

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('Recordatorio', email.subject)
        self.assertEqual(email.to, ['tutor.deuda@test.com'])
        self.assertIn('$42.000,00', email.body)
        self.assertIn('Lucas Gómez', email.body)

    def test_enviar_recordatorios_deuda_excluye_comprobantes_en_revision(self):
        cuota = Cuota.objects.create(
            periodo='Noviembre 2026',
            monto=25000,
            monto_total=25000,
            estado='Pendiente',
            fecha_vencimiento=date(2026, 11, 10),
            id_tutor=self.tutor,
            id_legajo_alumno=self.alumno,
        )
        solicitud = PagoPendiente.objects.create(
            id_tutor=self.tutor,
            legajo_alumno=self.alumno,
            mes='Noviembre 2026',
            importe=25000,
            estado='En revisión',
            fecha_solicitud=timezone.now(),
        )
        pago = PagoCuota.objects.create(
            cuota=cuota,
            solicitud=solicitud,
            tutor=self.tutor,
            importe=25000,
            medio_pago='Transferencia',
            estado='En revisión',
        )
        ComprobantePago.objects.create(
            cuota=cuota,
            pago=pago,
            archivo='comprobantes/test.pdf',
            estado='En revisión',
        )

        mail.outbox.clear()
        call_command('enviar_recordatorios_deuda', periodo='Noviembre 2026')

        # No debe enviar email porque el saldo de 25000 está cubierto por comprobante en revisión
        self.assertEqual(len(mail.outbox), 0)

    def test_reportes_administrativos_endpoints_y_permisos(self):
        # 1. Admin accede a reportes de ingresos
        res_ingresos = self.api_client.get(
            '/api/reportes/ingresos/?mes=11&anio=2026',
            HTTP_AUTHORIZATION=f'Bearer {self.admin_token}',
        )
        self.assertEqual(res_ingresos.status_code, 200)
        self.assertIn('total_recaudado', res_ingresos.data)
        self.assertIn('porcentaje_cobranza', res_ingresos.data)

        # 2. Admin accede a pagos completos e incompletos
        res_completos = self.api_client.get(
            '/api/reportes/pagos-completos/?mes=11&anio=2026',
            HTTP_AUTHORIZATION=f'Bearer {self.admin_token}',
        )
        self.assertEqual(res_completos.status_code, 200)
        self.assertIsInstance(res_completos.data, list)

        res_incompletos = self.api_client.get(
            '/api/reportes/pagos-incompletos/?mes=11&anio=2026',
            HTTP_AUTHORIZATION=f'Bearer {self.admin_token}',
        )
        self.assertEqual(res_incompletos.status_code, 200)
        self.assertIsInstance(res_incompletos.data, list)

        # 3. Tutor es rechazado con 403 Forbidden en los reportes de admin
        res_rechazo = self.api_client.get(
            '/api/reportes/ingresos/',
            HTTP_AUTHORIZATION=f'Bearer {self.tutor_token}',
        )
        self.assertEqual(res_rechazo.status_code, 403)

    def test_reportes_tutor_facturas_y_deuda_discriminada(self):
        cuota = Cuota.objects.create(
            periodo='Noviembre 2026',
            monto=25000,
            monto_total=42000,
            estado='Pendiente',
            fecha_vencimiento=date(2026, 11, 10),
            id_tutor=self.tutor,
            id_legajo_alumno=self.alumno,
        )

        # Consulta de facturas del tutor
        res_facturas = self.api_client.get(
            '/api/facturas/',
            HTTP_AUTHORIZATION=f'Bearer {self.tutor_token}',
        )
        self.assertEqual(res_facturas.status_code, 200)
        self.assertEqual(len(res_facturas.data), 1)
        self.assertEqual(res_facturas.data[0]['id'], cuota.id_cuota)
        self.assertEqual(res_facturas.data[0]['alumno_nombre'], 'Lucas Gómez')

        # Consulta de historial discriminado del tutor
        res_deuda = self.api_client.get(
            '/api/deuda/historial/',
            HTTP_AUTHORIZATION=f'Bearer {self.tutor_token}',
        )
        self.assertEqual(res_deuda.status_code, 200)
        self.assertEqual(res_deuda.data['tutor_id'], self.tutor.id)
        self.assertEqual(Decimal(res_deuda.data['total_deuda']), 42000)
        self.assertEqual(Decimal(res_deuda.data['deuda_cuota_base']), 25000)
        self.assertEqual(Decimal(res_deuda.data['deuda_transporte']), 8000)
        self.assertEqual(Decimal(res_deuda.data['deuda_comedor']), 5000)
        self.assertEqual(Decimal(res_deuda.data['deuda_deportes']), 4000)
        self.assertEqual(len(res_deuda.data['desglose_alumnos']), 1)

