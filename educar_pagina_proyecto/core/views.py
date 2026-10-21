import requests
from django.http import JsonResponse
import re
from django.core.files.storage import FileSystemStorage
from datetime import datetime, date, time
from django.conf import settings
from datetime import date
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
import re
import resend
import os
from django.shortcuts import render, redirect
from django.db.models import Avg
from django.db import transaction, IntegrityError
import json
from django.core.mail import EmailMessage
from django.contrib import messages
from django.contrib.messages import get_messages
from django.utils import timezone
from datetime import date
from django.views.decorators.cache import never_cache
from django.shortcuts import get_object_or_404, redirect
from .models import (
    Inscripcion,
    Materia,
    Curso,
    Usuario,
    Persona,
    Directivo,
    Docente,
    Alumno,
    Preceptor,
    Curso,
    Tutor,
    TutorTutoraAlumno,
    PersonalAdministrativo,
    Noticia,
    Calificacion,
    Asistencia,
    CursoCursaMaterias,
    DocenteDictaMateria,
    DisciplinaDeportiva,
    Reserva,
    Instalacion,
    Persona,
    Cuota,
    PostulacionLaboral,
    SolicitudInscripcion,
    PagoPendiente,
    Arancel,
    DocumentacionAlumno,
    Tarea,
    DocenteDisciplina,
    NivelEducativo,
    GrupoDeportivo,
    InscripcionDeportiva,
    Horario,
)
COMUNICADOS_FILE = os.path.join(
    os.path.dirname(__file__),
    'comunicados.json'
)
import json
import os
from django.db.models import Avg
from django.views.decorators.cache import never_cache

OPINIONES_FILE = os.path.join(os.path.dirname(__file__), 'opiniones.json')

def obtener_persona(request):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        return None

    usuario = Usuario.objects.get(id=usuario_id)
    return Persona.objects.filter(id_usuario=usuario).first()

def index(request):
    usuario_datos = Usuario.objects.all()
    persona, dashboard_url = obtener_datos_sesion(request)
    return render(request, 'core/index.html', {
        'usuarios': usuario_datos,
        'persona': persona,
        'dashboard_url': dashboard_url
    })

def bienestar(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    return render(request, 'core/bienestar.html', {
        'persona': persona,
        'dashboard_url': dashboard_url
    })

def contacto(request):
    opiniones = []

    if os.path.exists(OPINIONES_FILE):
        try:
            with open(OPINIONES_FILE, 'r', encoding='utf-8') as f:
                contenido = f.read().strip()

                if contenido:
                    opiniones = json.loads(contenido)
                    opiniones.reverse()

        except (json.JSONDecodeError, FileNotFoundError):
            opiniones = []

    persona, dashboard_url = obtener_datos_sesion(request)

    return render(request, 'core/contacto.html', {
        'opiniones': opiniones,
        'persona': persona,
        'dashboard_url': dashboard_url
    })

_NOMBRE_REGEX = re.compile(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]+$')
_DNI_REGEX = re.compile(r'^\d{7,8}$')
_TELEFONO_REGEX = re.compile(r'^\d{8,15}$')
_RANGOS_NIVEL = {
    'inicial': (3, 5, 'Inicial'),
    'primario': (6, 11, 'Primario'),
    'secundario': (12, 18, 'Secundario'),
}


def _calcular_edad(fecha_nacimiento):
    hoy = date.today()
    edad = hoy.year - fecha_nacimiento.year
    if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        edad -= 1
    return edad


def _validar_datos_inscripcion(post):
    errores = []

    campos_nombre = (
        ('nombre', 'El nombre'),
        ('apellido', 'El apellido'),
        ('tutor', 'El nombre del tutor'),
        ('apellido_tutor', 'El apellido del tutor'),
    )
    for campo, etiqueta in campos_nombre:
        valor = (post.get(campo) or '').strip()
        if not valor:
            errores.append(f'{etiqueta} es obligatorio.')
        elif not _NOMBRE_REGEX.match(valor):
            errores.append(f'{etiqueta} solo puede contener letras.')

    for campo, etiqueta in (('dni', 'El DNI'), ('dni_tutor', 'El DNI del tutor')):
        valor = (post.get(campo) or '').strip()
        if not _DNI_REGEX.match(valor):
            errores.append(f'{etiqueta} debe tener 7 u 8 dígitos numéricos.')

    direccion = (post.get('direccion') or '').strip()
    if not direccion:
        errores.append('La dirección del estudiante es obligatoria.')

    telefono = (post.get('telefono') or '').strip()
    if not _TELEFONO_REGEX.match(telefono):
        errores.append(
            'El teléfono debe contener solo números (entre 8 y 15 dígitos).'
        )

    telefono_alumno = (post.get('telefono_alumno') or '').strip()
    if telefono_alumno and not _TELEFONO_REGEX.match(telefono_alumno):
        errores.append(
            'El teléfono del alumno debe contener solo números (entre 8 y 15 dígitos).'
        )

    nivel = post.get('nivel')
    fecha_str = post.get('fecha')
    if fecha_str and nivel in _RANGOS_NIVEL:
        try:
            fecha_nac = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            edad = _calcular_edad(fecha_nac)
            min_edad, max_edad, label = _RANGOS_NIVEL[nivel]
            if edad < min_edad or edad > max_edad:
                errores.append(
                    f'La edad ({edad} años) no corresponde al Nivel {label} '
                    f'(de {min_edad} a {max_edad} años).'
                )
        except ValueError:
            errores.append('La fecha de nacimiento no es válida.')

    return errores


def inscripcion(request):
    # 1. Obtenemos los datos de sesión al inicio de la función
    persona, dashboard_url = obtener_datos_sesion(request)

    if request.method == 'POST':
        errores = _validar_datos_inscripcion(request.POST)
        if errores:
            return render(
                request,
                'core/inscripcion.html',
                {
                    'error': ' '.join(errores),
                    'persona': persona,
                    'dashboard_url': dashboard_url,
                },
            )

        SolicitudInscripcion.objects.create(
            nombre_alumno=request.POST.get('nombre'),
            apellido_alumno=request.POST.get('apellido'),
            dni_alumno=request.POST.get('dni'),
            fecha_nacimiento=request.POST.get('fecha'),
            direccion=request.POST.get('direccion'),
            telefono_alumno=request.POST.get('telefono_alumno'),
            email_alumno=request.POST.get('email_alumno'),

            nivel=request.POST.get('nivel'),
            turno=request.POST.get('turno'),

            nombre_tutor=request.POST.get('tutor'),
            apellido_tutor=request.POST.get('apellido_tutor'),
            dni_tutor=request.POST.get('dni_tutor'),

            parentesco=request.POST.get('parentesco'),

            telefono=request.POST.get('telefono'),
            email=request.POST.get('email'),
            
            direccion_tutor=request.POST.get("direccion_tutor"),

            observaciones=request.POST.get('observaciones'),

            fecha_solicitud=timezone.now(),

            estado='Pendiente'
        )

        return render(
            request,
            'core/inscripcion.html',
            {
                'exito': True,
                'persona': persona,
                'dashboard_url': dashboard_url
            }
        )

    return render(
        request,
        'core/inscripcion.html',
        {
            'persona': persona,
            'dashboard_url': dashboard_url
        }
    )

@never_cache
def login(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if persona and dashboard_url and dashboard_url != 'login':
        return redirect(dashboard_url)

    if request.method == 'POST':
        usuario_input = request.POST.get('usuario')
        password = request.POST.get('password')
        rol_input = request.POST.get('rol')

        if not rol_input:
            return render(request, 'core/login.html', {
                'error': 'Debe seleccionar un tipo de usuario.'
            })
        try:
            try:
                usuario = Usuario.objects.get(
                    nombre_usuario=usuario_input,
                    contrasenia=password
                )
            except Usuario.DoesNotExist:
                usuario = Usuario.objects.get(
                    correo=usuario_input,
                    contrasenia=password
                )

            # 🔥 DETECTAR ROL POR TABLAS
            redireccion = 'login'
            rol_correcto = False
            
            if rol_input == 'administrativo' and PersonalAdministrativo.objects.filter(id_persona__id_usuario=usuario).exists():
                rol_correcto = True
                redireccion = 'dashboard-administrativo'
                
            elif rol_input == 'docente' and Docente.objects.filter(id_persona__id_usuario=usuario).exists():
                rol_correcto = True
                redireccion = 'dashboard-docente'
                
            elif rol_input == 'padre' and Tutor.objects.filter(id_persona__id_usuario=usuario).exists():
                rol_correcto = True
                redireccion = 'dashboard-padres'
                
            elif rol_input == 'preceptor' and Preceptor.objects.filter(id_persona__id_usuario=usuario).exists():
                rol_correcto = True
                redireccion = 'dashboard-preceptor'
                
            elif rol_input == 'directivo' and Directivo.objects.filter(id_persona__id_usuario=usuario).exists():
                rol_correcto = True
                redireccion = 'dashboard-directivo'
                
            elif rol_input == 'alumno' and Alumno.objects.filter(id_persona__id_usuario=usuario).exists():
                rol_correcto = True
                redireccion = 'dashboard-alumno'

            if not rol_correcto:
                return render(request, 'core/login.html', {
                    'error': 'El tipo de usuario seleccionado no corresponde a esta cuenta.'
                })

            request.session['usuario_id'] = usuario.id
            return redirect(redireccion)
        except Usuario.DoesNotExist:
            return render(request, 'core/login.html', {
                'error': 'Datos incorrectos'
            })

    return render(request, 'core/login.html')

@never_cache
def niveles(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    return render(request, 'core/niveles.html', {
        'persona': persona,
        'dashboard_url': dashboard_url
    })

def noticias(request):
    noticias = Noticia.objects.all().order_by('-id_noticia')
    persona, dashboard_url = obtener_datos_sesion(request)
    return render(request, 'core/noticias.html', {
        'noticias': noticias,
        'persona': persona,
        'dashboard_url': dashboard_url
    })

def _grupos_deportivos_en_conflicto(grupo, inscripciones):
    for inscripcion in inscripciones:
        otro = inscripcion.id_grupo
        if grupo.dia_semana == otro.dia_semana and max(grupo.hora_inicio, otro.hora_inicio) < min(grupo.hora_fin, otro.hora_fin):
            return otro
    return None


@never_cache
def baja_inscripcion_deportiva(request, id_inscripcion):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona or dashboard_url != 'dashboard-alumno':
        return redirect('login')
    if request.method == 'POST':
        alumno = get_object_or_404(Alumno, id_persona=persona)
        inscripcion = get_object_or_404(
            InscripcionDeportiva,
            id_inscripcion=id_inscripcion,
            id_alumno=alumno,
            estado='Activa',
        )
        inscripcion.estado = 'Cancelada'
        inscripcion.save(update_fields=['estado'])
        messages.success(request, 'Te desinscribiste del deporte correctamente.')
    request.session['panel_activo'] = 'deportes'
    return redirect('dashboard-alumno')


@never_cache
def dashboard_alumno(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona:
        return redirect('login')
    if dashboard_url != 'dashboard-alumno':
        return redirect(dashboard_url)
        
    alumno = Alumno.objects.filter(
        id_persona=persona
    ).select_related(
        'id_curso',
        'id_disciplina',
        'id_disciplina__id_instalacion',
    ).first()
    
    if alumno and alumno.estado == 'Inactivo':
        # Cerrar sesión para que no pueda volver a entrar
        if 'usuario_id' in request.session:
            del request.session['usuario_id']
        
        return render(request, 'core/alumno-inactivo.html')

    if not alumno:
        return redirect('login')

    if request.method == 'POST' and request.POST.get('accion') == 'inscribir_deporte':
        request.session['panel_activo'] = 'deportes'
        id_grupo = request.POST.get('id_grupo')
        if not id_grupo:
            messages.error(request, 'Debes seleccionar un grupo deportivo.')
            return redirect('dashboard-alumno')

        grupo_elegido = GrupoDeportivo.objects.select_related(
            'id_disciplina', 'nivel_educativo', 'profesor_responsable'
        ).filter(id_grupo=id_grupo, estado='Activo').first()
        if not grupo_elegido:
            messages.error(request, 'El grupo deportivo seleccionado no existe o no está activo.')
            return redirect('dashboard-alumno')
        if alumno.id_curso and (alumno.id_curso.turno or '').strip().lower() == grupo_elegido.turno.strip().lower():
            messages.error(request, 'El deporte debe estar en el turno contrario al curso del alumno.')
            return redirect('dashboard-alumno')

        inscripciones_actuales = list(InscripcionDeportiva.objects.filter(
            id_alumno=alumno, estado='Activa'
        ).select_related('id_grupo', 'id_grupo__id_disciplina'))
        if any(i.id_grupo_id == grupo_elegido.id_grupo for i in inscripciones_actuales):
            messages.info(request, f'Ya estás inscripto en {grupo_elegido.id_disciplina.nombre}.')
            return redirect('dashboard-alumno')
        if len(inscripciones_actuales) >= 2:
            messages.error(request, 'Cada alumno puede inscribirse como máximo en dos deportes.')
            return redirect('dashboard-alumno')
        if grupo_elegido.cupo_maximo is not None and grupo_elegido.inscripciones.filter(estado='Activa').count() >= grupo_elegido.cupo_maximo:
            messages.error(request, 'El grupo deportivo ya alcanzó su cupo máximo.')
            return redirect('dashboard-alumno')
        conflicto = _grupos_deportivos_en_conflicto(grupo_elegido, inscripciones_actuales)
        if conflicto:
            messages.error(request, f'El horario se superpone con {conflicto.id_grupo.id_disciplina.nombre}.')
            return redirect('dashboard-alumno')

        InscripcionDeportiva.objects.create(id_alumno=alumno, id_grupo=grupo_elegido)
        if not alumno.id_disciplina_id:
            alumno.id_disciplina_id = grupo_elegido.id_disciplina_id
            alumno.save(update_fields=['id_disciplina'])
        messages.success(request, f'Te inscribiste correctamente en {grupo_elegido.id_disciplina.nombre}.')
        return redirect('dashboard-alumno')

    if request.method == 'POST' and request.FILES.get('justificacion'):

        asistencia_id = request.POST.get('asistencia_id')

        asistencia = Asistencia.objects.filter(
            id_asistencia=asistencia_id,
            legajo_alumno=alumno
        ).first()
        if not asistencia:
            request.session["panel_activo"] = "asistencia"
            messages.error(
                request,
                'No se encontró la asistencia seleccionada.'
            )
            return redirect('dashboard-alumno')
        if asistencia.archivo_justificacion:
            request.session["panel_activo"] = "asistencia"
            messages.error(
                request,
                'Esta asistencia ya posee una justificación.'
            )
            return redirect('dashboard-alumno')
        if asistencia:

            archivo = request.FILES['justificacion']
            extensiones_permitidas = [
                '.pdf',
                '.jpg',
                '.jpeg',
                '.png'
            ]
            tipos_permitidos = [
                'application/pdf',
                'image/jpeg',
                'image/png'
            ]

            if archivo.content_type not in tipos_permitidos:
                request.session["panel_activo"] = "asistencia"
                messages.error(
                    request,
                    'Tipo de archivo no válido.'
                )
                return redirect('dashboard-alumno')
            if archivo.size > 5 * 1024 * 1024:
                request.session["panel_activo"] = "asistencia"
                messages.error(
                    request,
                    'El archivo no puede superar los 5 MB.'
                )
                return redirect('dashboard-alumno')
            extension = os.path.splitext(
                archivo.name
            )[1].lower()

            if extension not in extensiones_permitidas:
                request.session["panel_activo"] = "asistencia"
                messages.error(
                    request,
                    'Solo se permiten archivos PDF, JPG, JPEG y PNG.'
                )
                return redirect('dashboard-alumno')
            nombre_alumno = (
                f"{persona.nombre}_{persona.apellido}"
                .replace(" ", "_")
            )

            curso = f"{alumno.id_curso.anio}{alumno.id_curso.comision}"

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            nombre_archivo = (
                f"{nombre_alumno}_{curso}_{asistencia.fecha}_{timestamp}"
                f"{extension}"
            )

            carpeta = os.path.join(
                settings.MEDIA_ROOT,
                'justificaciones'
            )

            os.makedirs(
                carpeta,
                exist_ok=True
            )

            fs = FileSystemStorage(
                location=carpeta
            )

            fs.save(
                nombre_archivo,
                archivo
            )

            asistencia.archivo_justificacion = (
                f"justificaciones/{nombre_archivo}"
            )

            asistencia.save()

            request.session["panel_activo"] = "asistencia"

            messages.success(
                request,
                'Justificación enviada correctamente.'
            )

            return redirect('dashboard-alumno')


    curso_alumno = f"{alumno.id_curso.nivel_educativo.nombre} {alumno.id_curso.anio}° {alumno.id_curso.comision}"
    
    materias = CursoCursaMaterias.objects.filter(
        id_curso=alumno.id_curso
    ).select_related('id_materia').prefetch_related('horarios_normalizados')
    
    # Procesar horarios para mostrar en el panel
    # Inicializar días en orden
    horario_por_dia = {
        'lunes': [],
        'martes': [],
        'miércoles': [],
        'jueves': [],
        'viernes': []
    }

    # Función para normalizar nombres de días (maneja variantes sin tilde)
    def _normalize_dia(dia_raw):
        d = dia_raw.strip().lower()
        if d in ('miercoles', 'miercoles'):
            return 'miércoles'
        if d == 'miercoles':
            return 'miércoles'
        # cubrir otras variantes comunes
        mapping = {
            'lunes': 'lunes',
            'martes': 'martes',
            'miércoles': 'miércoles',
            'miercoles': 'miércoles',
            'jueves': 'jueves',
            'viernes': 'viernes'
        }
        return mapping.get(d, d)

    # Llenar con datos de las materias
    for materia in materias:
        horarios_normalizados = list(materia.horarios_normalizados.all())
        if horarios_normalizados:
            horario_items = []
            for horario in horarios_normalizados:
                dia_norm = _normalize_dia(horario.dia_semana)
                hora = f'{horario.hora_inicio.strftime("%H:%M")} - {horario.hora_fin.strftime("%H:%M")}'
                horario_items.append(f'{dia_norm.capitalize()}: {hora}')
                if dia_norm in horario_por_dia:
                    horario_por_dia[dia_norm].append({'materia': materia.id_materia.nombre, 'hora': hora})
            materia.horario_formateado = ' | '.join(horario_items)
        elif materia.horarios:
            try:
                horarios = json.loads(materia.horarios)

                # Crear formato legible
                horario_items = []
                for dia, hora in horarios.items():
                    dia_norm = _normalize_dia(dia)
                    horario_items.append(f"{dia_norm.capitalize()}: {hora}")

                    # Agregar a la lista de horarios por día si corresponde
                    if dia_norm in horario_por_dia:
                        horario_por_dia[dia_norm].append({
                            'materia': materia.id_materia.nombre,
                            'hora': hora
                        })

                materia.horario_formateado = " | ".join(horario_items)

            except Exception:
                materia.horario_formateado = str(materia.horarios)
        else:
            materia.horario_formateado = "Sin horario"

    inscripciones_deportivas = list(InscripcionDeportiva.objects.filter(
        id_alumno=alumno, estado='Activa'
    ).select_related(
        'id_grupo', 'id_grupo__id_disciplina', 'id_grupo__id_disciplina__id_instalacion',
        'id_grupo__nivel_educativo', 'id_grupo__profesor_responsable__id_persona'
    ).order_by('id_grupo__dia_semana', 'id_grupo__hora_inicio'))
    grupos_inscriptos_ids = {inscripcion.id_grupo_id for inscripcion in inscripciones_deportivas}
    disciplina = inscripciones_deportivas[0].id_grupo.id_disciplina if inscripciones_deportivas else alumno.id_disciplina
    for inscripcion in inscripciones_deportivas:
        grupo = inscripcion.id_grupo
        dia = grupo.dia_semana.strip().lower()
        dia = 'miércoles' if dia == 'miercoles' else dia
        if dia in horario_por_dia:
            horario_por_dia[dia].append({
                'materia': grupo.id_disciplina.nombre,
                'hora': f'{grupo.hora_inicio.strftime("%H:%M")} a {grupo.hora_fin.strftime("%H:%M")}',
                'es_deporte': True,
            })
    disciplina_horario_formateado = "Sin horario"

    if disciplina:
        if disciplina.horarios:
            try:
                horarios_disciplina = json.loads(disciplina.horarios)
                horario_items = []
                for dia, hora in horarios_disciplina.items():
                    dia_norm = _normalize_dia(dia)
                    horario_items.append(f"{dia_norm.capitalize()}: {hora}")

                    if dia_norm in horario_por_dia:
                        horario_por_dia[dia_norm].append({
                            'materia': disciplina.nombre,
                            'hora': hora,
                            'es_deporte': True,
                        })

                disciplina_horario_formateado = " | ".join(horario_items)
            except Exception:
                disciplina_horario_formateado = str(disciplina.horarios)

    grupos_deportivos = GrupoDeportivo.objects.filter(
        estado='Activo', nivel_educativo_id=alumno.id_curso.nivel_educativo_id
    ).select_related(
        'id_disciplina', 'id_disciplina__id_instalacion', 'nivel_educativo',
        'profesor_responsable__id_persona'
    ).order_by('id_disciplina__nombre', 'nivel_educativo__nombre', 'dia_semana', 'hora_inicio')
    for grupo in grupos_deportivos:
        grupo.horario_formateado = f'{grupo.dia_semana.capitalize()} {grupo.hora_inicio.strftime("%H:%M")} a {grupo.hora_fin.strftime("%H:%M")}'
        grupo.nombre = grupo.id_disciplina.nombre
        grupo.id_instalacion = grupo.id_disciplina.id_instalacion
        grupo.esta_inscripto = grupo.id_grupo in grupos_inscriptos_ids
            
    
    tutor_relacion = TutorTutoraAlumno.objects.filter(
        id_alumno=alumno
    ).select_related(
        'id_tutor',
        'id_tutor__id_persona'
    ).first()

    
    calificaciones = Calificacion.objects.filter(
        legajo_alumno=alumno
    ).select_related('id_materia')

    asistencias = Asistencia.objects.filter(
        legajo_alumno=alumno
    ).order_by('-fecha')

    presentes = asistencias.filter(
        tipo_asistencia='Presente'
    ).count()

    ausencias = asistencias.filter(
        tipo_asistencia='Ausente'
    ).count()

    tardanzas = asistencias.filter(
        tipo_asistencia='Tardanza'
    ).count()

    # Porcentaje de asistencia (presente / total registros)
    total_asistencias = presentes + ausencias + tardanzas
    if total_asistencias > 0:
        asistencia_pct = round((presentes / total_asistencias) * 100)
    else:
        asistencia_pct = 0

    # Agrupar calificaciones por materia para el panel de notas
    from collections import OrderedDict

    from collections import OrderedDict

    notas_resumen = []
    # Iterar por las materias asignadas al curso
    for curso_materia in materias:
        mat = curso_materia.id_materia
        califs_mat = calificaciones.filter(id_materia=mat).order_by('fecha')

        trim1 = ''
        trim2 = ''
        trim3 = ''
        numeric_notes = []
        estado = ''

        for c in califs_mat:
            display_val = float(c.nota) if c.nota is not None else (c.tipo_evaluacion or '')

            # Asignar según tipo de evaluación
            if c.tipo_evaluacion == '1° Bimestre':
                trim1 = display_val
            elif c.tipo_evaluacion == '2° Bimestre':
                trim2 = display_val
            elif c.tipo_evaluacion == '3° Bimestre':
                trim3 = display_val
            else:
                # Fallback por compatibilidad
                if not trim1:
                    trim1 = display_val
                elif not trim2:
                    trim2 = display_val
                elif not trim3:
                    trim3 = display_val

            if c.nota is not None:
                try:
                    numeric_notes.append(float(c.nota))
                except Exception:
                    pass

            if c.tipo_evaluacion and 'aprob' in c.tipo_evaluacion.lower():
                estado = 'Aprobado'

        promedio_mat = round(sum(numeric_notes) / len(numeric_notes), 2) if numeric_notes else ''

        notas_resumen.append({
            'materia': mat.nombre,
            'trim1': trim1,
            'trim2': trim2,
            'trim3': trim3,
            'promedio': promedio_mat,
            'estado': estado or 'En curso'
        })

    # Promedio general del alumno (promedio de todas las calificaciones numéricas)
    all_numeric = [float(c.nota) for c in calificaciones if c.nota is not None]
    promedio_general = round(sum(all_numeric) / len(all_numeric), 1) if all_numeric else 0

    # Materias aprobadas: sólo se cuentan si hay un registro cuyo tipo indica 'Aprobado'
    materias_aprobadas = sum(1 for n in notas_resumen if n.get('estado') == 'Aprobado')
    total_materias = len(notas_resumen)
    COMUNICADOS_FILE = os.path.join(
        settings.BASE_DIR,
        "core",
        "comunicados.json"
    )

    comunicados_alumno = []
    ultimos_comunicados = []

    if os.path.exists(COMUNICADOS_FILE):
        try:
            with open(COMUNICADOS_FILE, 'r', encoding='utf-8') as f:
                file_content = f.read().strip()
                comunicados = json.loads(file_content) if file_content else []

                comunicados_alumno = [
                    c for c in comunicados
                    if (
                        c.get('rol') == 'Directivo'
                        or (
                            c.get('rol') == 'Preceptor'
                            and c.get('curso', '').strip().lower() == curso_alumno.strip().lower()
                        )
                    )
                ]

                
                comunicados_alumno.reverse()

            
            ultimos_comunicados = comunicados_alumno[:3]

        except json.JSONDecodeError:
            comunicados_alumno = []
            ultimos_comunicados = []
    
    tareas_alumno = []
    if materias.exists():
        for curso_materia in materias:
            materia_real = curso_materia.id_materia
            tarea_materia = Tarea.objects.filter(
                materia=materia_real,
                curso_destinado=alumno.id_curso
            ).select_related('docente', 'docente__id_persona', 'curso_destinado').order_by('-fecha_creacion')
            
            for tarea in tarea_materia:
                tareas_alumno.append({
                    'tarea': tarea,
                    'materia_nombre': materia_real.nombre,
                    'docente_nombre': f'{tarea.docente.id_persona.apellido} {tarea.docente.id_persona.nombre}',
                    'curso_destinado': tarea.curso_destinado.comision if tarea.curso_destinado else '-',
                })
    tareas_alumno.sort(key=lambda x: x['tarea'].fecha_creacion, reverse=True)

    panel_activo = request.session.pop("panel_activo", "inicio")
    mensajes = list(get_messages(request))
    hay_horarios = any(clases for clases in horario_por_dia.values())
    
    alumno = Alumno.objects.select_related(
        'id_curso'
    ).get(
        id_persona=persona
    )
    return render(request, 'core/dashboard-alumno.html', {
        'persona': persona,
        'alumno': alumno,
        'comunicados': comunicados_alumno,
        'ultimas_noticias': ultimos_comunicados,
        'calificaciones': calificaciones,
        'asistencias': asistencias,
        'presentes': presentes,
        'ausencias': ausencias,
        'tardanzas': tardanzas,
        'promedio_general': promedio_general,
        'asistencia_pct': asistencia_pct,
        'materias_aprobadas': materias_aprobadas,
        'total_materias': total_materias,
        'notas_resumen': notas_resumen,
        'materias': materias,
        'disciplina': disciplina,
        'inscripciones_deportivas': inscripciones_deportivas,
        'grupos_inscriptos_ids': grupos_inscriptos_ids,
        'disciplina_horario_formateado': disciplina_horario_formateado,
        'disciplinas_disponibles': grupos_deportivos,
        'tutor_relacion': tutor_relacion,
        'horario_por_dia': horario_por_dia,
        'hay_horarios': hay_horarios,
        "panel_activo": panel_activo,
        'messages': mensajes,
        'tareas_alumno': tareas_alumno,
    })

@never_cache
def dashboard_docente(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona:
        return redirect('login')
    if dashboard_url != 'dashboard-docente':
        return redirect(dashboard_url)
    from django.db.models import Avg
    
    docente = Docente.objects.filter(id_persona=persona).first()

    asignaciones = DocenteDictaMateria.objects.filter(id_docente=docente)
    asignaciones_directas = asignaciones.exclude(id_curso__isnull=True)
    if asignaciones_directas.exists():
        materias = Materia.objects.filter(
            id_materia__in=asignaciones_directas.values('id_materia_id')
        ).distinct()
        cursos = Curso.objects.filter(
            id_curso__in=asignaciones_directas.values('id_curso_id')
        ).distinct()
    else:
        materias = Materia.objects.filter(
            docentedictamateria__id_docente=docente
        ).distinct()
        cursos = Curso.objects.filter(
            cursocursamaterias__id_materia__in=materias
        ).distinct()

    alumnos = Alumno.objects.filter(
        id_curso__in=cursos
    ).distinct()

    tareas = Tarea.objects.filter(docente=docente).select_related('curso_destinado', 'materia').order_by('-fecha_creacion')

    # calificaciones
    calificaciones = Calificacion.objects.filter(
        id_materia__in=materias,
        legajo_alumno__in=alumnos
    ).select_related('id_materia', 'legajo_alumno')

    # diccionario de notas
    # diccionario de notas (agrupado por tipo de bimestre)
    # diccionario de notas (agrupado por tipo de bimestre)
    notas_por_alumno = {}
    for c in calificaciones:
        alumno_id = c.legajo_alumno_id
        
        # Crear entrada si no existe
        if alumno_id not in notas_por_alumno:
            notas_por_alumno[alumno_id] = {'trim1': '', 'trim2': '', 'trim3': ''}

        val_nota = float(c.nota) if c.nota is not None else ''
        
        # Asignar nota según el tipo de evaluación
        if c.tipo_evaluacion == '1° Bimestre':
            notas_por_alumno[alumno_id]['trim1'] = str(val_nota)  # Convertir a string para mostrar
        elif c.tipo_evaluacion == '2° Bimestre':
            notas_por_alumno[alumno_id]['trim2'] = str(val_nota)
        elif c.tipo_evaluacion == '3° Bimestre':
            notas_por_alumno[alumno_id]['trim3'] = str(val_nota)
    # cursos
    cursos_data = []
    for curso in cursos:
        alumnos_count = Alumno.objects.filter(id_curso=curso).count()
        promedio = Calificacion.objects.filter(
            legajo_alumno__id_curso=curso
        ).aggregate(prom=Avg('nota'))['prom']
        cursos_data.append({
            'curso': f"{getattr(curso, 'anio', '')}° {getattr(curso, 'comision', '')}",
            'nivel': getattr(curso.nivel_educativo, 'nombre', ''),
            'turno': getattr(curso, 'turno', ''),
            'alumnos': alumnos_count,
            'promedio': round(promedio, 1) if promedio else 0,
        })

    # horarios
    horarios = CursoCursaMaterias.objects.filter(
        id_materia__in=materias,
        id_curso__in=cursos,
    ).select_related('id_curso', 'id_materia')

    horario_dict = {}
    for h in horarios:
        data = h.horarios
        if isinstance(data, str):
            data = json.loads(data)
        for dia, rango in data.items():
            if rango not in horario_dict:
                horario_dict[rango] = {
                    'Lunes': '-',
                    'Martes': '-',
                    'Miércoles': '-',
                    'Jueves': '-',
                    'Viernes': '-',
                }
            dia_cap = dia.capitalize()
            if dia_cap == 'Miercoles':
                dia_cap = 'Miércoles'
            horario_dict[rango][dia_cap] = f"{h.id_curso.anio}° {h.id_curso.nivel_educativo.nombre} ({h.id_curso.comision}) - {h.id_curso.turno}"
    cantidad_tareas = tareas.count()
    return render(request, 'core/dashboard-docente.html', {
        'persona': persona,
        'docente': docente,
        'materias': materias,
        'cursos': cursos_data,
        'cursos_lista': cursos,       
        'alumnos': alumnos,
        'calificaciones': calificaciones,
        'notas_por_alumno': notas_por_alumno,
        'horario': horario_dict,
        'tareas': tareas,        
        'cantidad_tareas': cantidad_tareas,     
    })


def horario_docente(request):
    persona = obtener_persona(request)

    if not persona:
        return redirect('login')

    docente = Docente.objects.filter(id_persona=persona).first()

    if not docente:
        return redirect('login')

    asignaciones = DocenteDictaMateria.objects.filter(id_docente=docente)
    asignaciones_directas = asignaciones.exclude(id_curso__isnull=True)
    if asignaciones_directas.exists():
        materias = Materia.objects.filter(
            id_materia__in=asignaciones_directas.values('id_materia_id')
        ).distinct()
        cursos = CursoCursaMaterias.objects.filter(
            id_curso__in=asignaciones_directas.values('id_curso_id'),
            id_materia__in=asignaciones_directas.values('id_materia_id'),
        )
    else:
        materias = Materia.objects.filter(
            docentedictamateria__id_docente=docente
        ).distinct()
        cursos = CursoCursaMaterias.objects.filter(
            id_materia__in=materias
        )

    horario = {}

    for c in cursos:
        data = c.horarios

        if isinstance(data, str):
            data = json.loads(data)

        for dia, rango in data.items():
            if rango not in horario:
                horario[rango] = {
                    "Lunes": "-",
                    "Martes": "-",
                    "Miércoles": "-",
                    "Jueves": "-",
                    "Viernes": "-"
                }

            dia_cap = dia.capitalize()

            if dia_cap == "Miercoles":
                dia_cap = "Miércoles"

            horario[rango][dia_cap] = c.id_curso.comision

    return render(request, "tu_template.html", {
        "horario": horario
    })

@never_cache
def dashboard_directivo(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona:
        return redirect('login')

    if dashboard_url != 'dashboard-directivo':
        return redirect(dashboard_url)

    cantidad_alumnos = Alumno.objects.count()
    cantidad_docentes = Docente.objects.count()
    cantidad_preceptores = Preceptor.objects.count()
    cantidad_administrativos = PersonalAdministrativo.objects.count()

    promedio_institucional = (
        Calificacion.objects.aggregate(
            promedio=Avg('nota')
        )['promedio'] or 0
    )

    ultimas_noticias = Noticia.objects.order_by('-fecha_publicacion')[:5]
    
    # 🔥 NUEVA LÓGICA: Agrupar materias por docente
    docentes_dict = {}
    
    relaciones = (
        DocenteDictaMateria.objects
        .select_related('id_docente__id_persona', 'id_materia')
    )

    for relacion in relaciones:
        docente = relacion.id_docente
        materia = relacion.id_materia
        docente_key = docente.pk 
        
        if docente_key not in docentes_dict:
            docentes_dict[docente_key] = {
                'nombre': f'{docente.id_persona.nombre} {docente.id_persona.apellido}',
                'materias': [],
                'cursos': set()
            }
        
        # Agregar materia
        docentes_dict[docente_key]['materias'].append(materia.nombre)
        
        # Las asignaciones nuevas indican el curso exacto; las antiguas
        # sin curso mantienen el comportamiento anterior por materia.
        if relacion.id_curso_id:
            cursos = [relacion.id_curso]
        else:
            cursos = [cm.id_curso for cm in CursoCursaMaterias.objects.filter(
                id_materia=materia
            ).select_related('id_curso')]

        for curso in cursos:
            curso_texto = f"{curso.anio}° {curso.comision} ({curso.nivel_educativo.nombre})"
            docentes_dict[docente_key]['cursos'].add(curso_texto)
    
    # Convertir el diccionario a lista
    docentes = []
    for docente_data in docentes_dict.values():
        docentes.append({
            'nombre': docente_data['nombre'],
            'materias': ', '.join(docente_data['materias']),
            'cursos': ', '.join(sorted(docente_data['cursos']))
        })
    
    # Ordenar por nombre
    docentes.sort(key=lambda x: x['nombre'])

    hoy = date.today()
    presentes = Asistencia.objects.filter(fecha=hoy, tipo_asistencia='Presente').count()
    ausentes = Asistencia.objects.filter(fecha=hoy, tipo_asistencia='Ausente').count()
    tardanzas = Asistencia.objects.filter(fecha=hoy, tipo_asistencia='Tardanza').count()
    
    alumnos_inicial = Alumno.objects.filter(id_curso__nivel_educativo__nombre='Inicial').count()
    alumnos_primario = Alumno.objects.filter(id_curso__nivel_educativo__nombre='Primario').count()
    alumnos_secundario = Alumno.objects.filter(id_curso__nivel_educativo__nombre='Secundario').count()
    
    solicitudes_pendientes = SolicitudInscripcion.objects.filter(estado='Pendiente').count()
    postulaciones = PostulacionLaboral.objects.count()
    
    iniciales = f"{persona.nombre[0].upper()}{persona.apellido[0].upper()}"
    
    return render(
        request,
        'core/dashboard-directivo.html',
        {
            'persona': persona,
            'cantidad_alumnos': cantidad_alumnos,
            'cantidad_docentes': cantidad_docentes,
            'cantidad_preceptores': cantidad_preceptores,
            'cantidad_administrativos': cantidad_administrativos,
            'promedio_institucional': round(promedio_institucional, 1),
            'ultimas_noticias': ultimas_noticias,
            'docentes': docentes,
            'presentes': presentes,
            'ausentes': ausentes,
            'tardanzas': tardanzas,
            'alumnos_inicial': alumnos_inicial,
            'alumnos_primario': alumnos_primario,
            'alumnos_secundario': alumnos_secundario,
            'solicitudes_pendientes': solicitudes_pendientes,
            'iniciales': iniciales,
            'postulaciones': postulaciones
        }
    )
    
def postulacion(request):
    return render(request, 'core/postulacion.html')

@never_cache
def enviar_postulacion(request):
    
    nombre = request.POST.get("nombre", "").strip()
    apellido = request.POST.get("apellido", "").strip()
    dni = request.POST.get("dni", "").strip()
    correo_postulante = request.POST.get("correo", "").strip()
    telefono = request.POST.get("telefono", "").strip()

    if request.method == "POST":

        nombre = request.POST.get("nombre")
        apellido = request.POST.get("apellido")
        dni = request.POST.get("dni")
        correo = request.POST.get("correo")
        telefono = request.POST.get("telefono")
        puesto = request.POST.get("puesto")
        mensaje = request.POST.get("mensaje")

        cv = request.FILES.get("cv")

        ruta_cv = None
        
        print("CORREO RECIBIDO:", repr(correo))
        
        print(
            "VALIDACION:",
            bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", correo))
)
        
        if not nombre.replace(" ", "").isalpha():
            print("Nombre inválido")
            return redirect('postulacion')

        if not apellido.replace(" ", "").isalpha():
            print("Apellido inválido")
            return redirect('postulacion')

        if not dni.isdigit():
            print("DNI inválido")
            return redirect('postulacion')

        if len(dni) < 7 or len(dni) > 8:
            print("DNI inválido")
            return redirect('postulacion')

        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", correo):
            print("Correo inválido")
            messages.error(request, "Ingrese un correo electrónico válido.")
            print("MENSAJE AGREGADO")
            return redirect('postulacion')

        if not telefono.isdigit():
            print("Teléfono inválido")
            return redirect('postulacion')

        if cv:
            fs = FileSystemStorage()
            nombre_archivo = fs.save(cv.name, cv)
            ruta_cv = fs.url(nombre_archivo)
            

        PostulacionLaboral.objects.create(
            nombre=nombre,
            apellido=apellido,
            dni=dni,
            correo=correo,
            telefono=telefono,
            puesto=puesto,
            mensaje=mensaje,
            cv=ruta_cv,
            fecha_postulacion=datetime.now()
        )

        print("Postulación guardada correctamente")
        
        correo = EmailMessage(
            subject=f"Nueva postulación - {nombre} {apellido}",
            body=f"""
        Nueva postulación recibida

        Nombre: {nombre}
        Apellido: {apellido}
        DNI: {dni}
        Correo: {correo}
        Teléfono: {telefono}
        Puesto: {puesto}

        Mensaje:
        {mensaje}
        """,
            from_email='educarparatransformarcolegio@gmail.com',
            to=['educarparatransformarcolegio@gmail.com']
        )
        
        if cv:
            correo.attach(
                cv.name,
                cv.read(),
                cv.content_type
            )
        
        correo.send()
        
        messages.success(
            request,
            "La postulación fue enviada correctamente. Nos pondremos en contacto si tu perfil coincide con una búsqueda."
        )

    return redirect('postulacion')

@never_cache
def enviar_consulta(request):

    if request.method == "POST":

        nombre = request.POST.get("nombre", "").strip()
        correo = request.POST.get("email", "").strip()
        mensaje = request.POST.get("mensaje", "").strip()
        origen = request.POST.get("origen", "contacto")

        # Nombre
        if not nombre.replace(" ", "").isalpha():
            messages.error(
                request,
                "El nombre solo puede contener letras."
            )
            return redirect('contacto')

        # Correo
        if not re.match(
            r"^[^@]+@[^@]+\.[^@]+$",
            correo
        ):
            messages.error(
                request,
                "Ingrese un correo electrónico válido."
            )
            return redirect('contacto')

        # Mensaje
        if not mensaje:
            messages.error(
                request,
                "Debe escribir una consulta."
            )
            return redirect('contacto')

        try:
            resend.api_key = os.environ.get("RESEND_API_KEY")

            resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": ["educarparatransformarcolegio@gmail.com"],
                "subject": f"Consulta desde la web - {nombre}",
                "html": f"""
                    <h2>Nueva consulta recibida</h2>
                    <p><strong>Nombre:</strong> {nombre}</p>
                    <p><strong>Correo:</strong> {correo}</p>
                    <p>{mensaje}</p>
                """
            })

        except Exception as e:
            print("ERROR RESEND:", e)
            raise

        messages.success(
            request,
            "La consulta fue enviada correctamente."
        )


        persona = obtener_persona(request)
        
        if origen == "contacto":
            return redirect("contacto")

        if persona:

            if Tutor.objects.filter(id_persona=persona).exists():
                request.session["panel_activo"] = "contacto"
                return redirect('dashboard-padres')

            if Alumno.objects.filter(id_persona=persona).exists():
                request.session["panel_activo"] = "contacto"
                return redirect('dashboard-alumno')

        return redirect('contacto')


@never_cache
def dashboard_administrativo(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona:
        return redirect('login')
    if dashboard_url != 'dashboard-administrativo':
        return redirect(dashboard_url)

    administrativo = PersonalAdministrativo.objects.filter(
        id_persona=persona
    ).first()

    instalaciones = Instalacion.objects.all()
    
    reservas = Reserva.objects.select_related(
        'id_instalacion',
        'id_persona_solicitante'
    ).all()
    
    if os.path.exists(OPINIONES_FILE):
        with open(OPINIONES_FILE, 'r', encoding='utf-8') as f:
            opiniones = json.load(f)
    else:
        opiniones = []
    
    cuotas = Cuota.objects.select_related(
        'id_tutor__id_persona',
        'id_legajo_alumno__id_persona'
    )
    
    cuotas_pendientes = PagoPendiente.objects.exclude(
        estado='Pagada'
    ).count()

    solicitudes = SolicitudInscripcion.objects.all().order_by('-fecha_solicitud')

    inscripciones_pendientes = SolicitudInscripcion.objects.filter(
        estado="Pendiente"
    ).count()
    
    pagos_pendientes = PagoPendiente.objects.all()
    documentacion_pendiente = DocumentacionAlumno.objects.filter(
        estado='Pendiente'
    ).count()
    documentaciones = DocumentacionAlumno.objects.filter(
        estado='Pendiente'
    ).order_by('-fecha_envio')

    niveles_educativos = NivelEducativo.objects.all().prefetch_related('cursos')
    cursos_academicos = Curso.objects.select_related('nivel_educativo').all().order_by(
        'nivel_educativo__nombre', 'anio', 'comision', 'turno'
    )
    materias_academicas = Materia.objects.all().prefetch_related(
        'cursocursamaterias_set', 'docentedictamateria_set'
    ).order_by('nombre')
    for materia in materias_academicas:
        materia.curso_ids = set(
            materia.cursocursamaterias_set.values_list('id_curso_id', flat=True)
        )
    deportes_academicos = DisciplinaDeportiva.objects.select_related('id_instalacion').all().order_by('nombre')
    grupos_deportivos_admin = GrupoDeportivo.objects.select_related(
        'id_disciplina', 'id_disciplina__id_instalacion', 'nivel_educativo',
        'profesor_responsable__id_persona'
    ).prefetch_related('inscripciones__id_alumno__id_persona').order_by(
        'id_disciplina__nombre', 'nivel_educativo__nombre', 'dia_semana', 'hora_inicio'
    )
    for grupo in grupos_deportivos_admin:
        grupo.inscriptos_activos = [
            inscripcion for inscripcion in grupo.inscripciones.all()
            if inscripcion.estado == 'Activa'
        ]
        grupo.cantidad_inscriptos = len(grupo.inscriptos_activos)
    alumnos_deportivos = Alumno.objects.select_related('id_persona').order_by(
        'id_persona__apellido', 'id_persona__nombre'
    )
    docentes_deportivos = Docente.objects.select_related('id_persona').order_by(
        'id_persona__apellido', 'id_persona__nombre'
    )
    cursos_materias_admin = CursoCursaMaterias.objects.select_related(
        'id_curso__nivel_educativo', 'id_materia'
    ).order_by('id_curso__nivel_educativo__nombre', 'id_curso__anio', 'id_curso__comision', 'id_materia__nombre')
    horarios_admin = Horario.objects.select_related(
        'curso_materia__id_curso__nivel_educativo', 'curso_materia__id_curso', 'curso_materia__id_materia',
        'grupo_deportivo__id_disciplina', 'grupo_deportivo__nivel_educativo',
    ).order_by('dia_semana', 'hora_inicio')
    
    panel_activo = request.session.pop("panel_activo", "inicio")
    mensajes = list(get_messages(request))
    
    return render(request, 'core/dashboard-administrativo.html', {
        'persona': persona,
        'administrativo': administrativo,
        'instalaciones': instalaciones,
        'reservas': reservas,
        'opiniones': opiniones,
        'cuotas': cuotas,
        'cuotas_pendientes': cuotas_pendientes,
        'solicitudes': solicitudes,
        'inscripciones_pendientes': inscripciones_pendientes,
        'pagos_pendientes': pagos_pendientes,
        'documentaciones': documentaciones,
        'documentacion_pendiente': documentacion_pendiente,
        'niveles_educativos': niveles_educativos,
        'cursos_academicos': cursos_academicos,
        'materias_academicas': materias_academicas,
        'deportes_academicos': deportes_academicos,
        'grupos_deportivos_admin': grupos_deportivos_admin,
        'alumnos_deportivos': alumnos_deportivos,
        'docentes_deportivos': docentes_deportivos,
        'cursos_materias_admin': cursos_materias_admin,
        'horarios_admin': horarios_admin,
        'panel_activo': panel_activo,
        'messages': mensajes,
    })


@never_cache
def lista_niveles_cursos_admin(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona or dashboard_url != 'dashboard-administrativo':
        return redirect('login')
    request.session['panel_activo'] = 'niveles-cursos'
    return redirect('dashboard-administrativo')


@never_cache
def lista_materias_admin(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona or dashboard_url != 'dashboard-administrativo':
        return redirect('login')
    request.session['panel_activo'] = 'materias'
    return redirect('dashboard-administrativo')


def _validar_acceso_niveles(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    return persona if persona and dashboard_url == 'dashboard-administrativo' else None


@never_cache
def alta_nivel_admin(request):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        descripcion = (request.POST.get('descripcion') or '').strip()
        estado = request.POST.get('estado', 'Activo')
        if not nombre:
            messages.error(request, 'El nombre del nivel es obligatorio.')
        elif NivelEducativo.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, 'Ya existe un nivel educativo con ese nombre.')
        else:
            NivelEducativo.objects.create(
                nombre=nombre.title(),
                descripcion=descripcion or None,
                estado=estado,
            )
            messages.success(request, 'Nivel educativo creado correctamente.')
    return redirect('lista-niveles-cursos-admin')


@never_cache
def modificar_nivel_admin(request, id_nivel):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    nivel = get_object_or_404(NivelEducativo, id_nivel=id_nivel)
    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        if not nombre:
            messages.error(request, 'El nombre del nivel es obligatorio.')
        elif NivelEducativo.objects.filter(nombre__iexact=nombre).exclude(id_nivel=id_nivel).exists():
            messages.error(request, 'Ya existe otro nivel educativo con ese nombre.')
        else:
            nivel.nombre = nombre.title()
            nivel.descripcion = (request.POST.get('descripcion') or '').strip() or None
            nivel.estado = request.POST.get('estado', 'Activo')
            nivel.save()
            messages.success(request, 'Nivel educativo actualizado correctamente.')
    return redirect('lista-niveles-cursos-admin')


@never_cache
def baja_nivel_admin(request, id_nivel):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        nivel = get_object_or_404(NivelEducativo, id_nivel=id_nivel)
        if nivel.cursos.exists():
            nivel.estado = 'Inactivo'
            nivel.save(update_fields=['estado'])
            messages.warning(request, 'El nivel tiene cursos asociados y fue marcado como inactivo.')
        else:
            nivel.delete()
            messages.success(request, 'Nivel educativo eliminado correctamente.')
    return redirect('lista-niveles-cursos-admin')


def _datos_curso(request):
    nivel_id = request.POST.get('nivel_educativo')
    anio = request.POST.get('anio')
    comision = (request.POST.get('comision') or '').strip()
    turno = (request.POST.get('turno') or '').strip()
    cupo = request.POST.get('cupo_maximo') or None
    if not nivel_id or not anio or not comision or not turno:
        raise ValueError('Nivel, año, comisión y turno son obligatorios.')
    try:
        nivel = NivelEducativo.objects.get(id_nivel=nivel_id, estado='Activo')
        anio = int(anio)
        if cupo:
            cupo = int(cupo)
    except (NivelEducativo.DoesNotExist, ValueError, TypeError):
        raise ValueError('Los datos del curso no son válidos.')
    if anio <= 0 or (cupo is not None and cupo <= 0):
        raise ValueError('El año y el cupo deben ser valores positivos.')
    return nivel, anio, comision, turno, cupo


@never_cache
def alta_curso_admin(request):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        try:
            nivel, anio, comision, turno, cupo = _datos_curso(request)
            if Curso.objects.filter(
                nivel_educativo=nivel, anio=anio, comision__iexact=comision, turno__iexact=turno
            ).exists():
                raise ValueError('Ya existe un curso con ese nivel, año, comisión y turno.')
            Curso.objects.create(
                nivel_educativo=nivel,
                anio=anio,
                comision=comision,
                turno=turno,
                cupo_maximo=cupo,
            )
            messages.success(request, 'Curso creado correctamente.')
        except (ValueError, IntegrityError) as error:
            messages.error(request, str(error))
    return redirect('lista-niveles-cursos-admin')


@never_cache
def modificar_curso_admin(request, id_curso):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    curso = get_object_or_404(Curso, id_curso=id_curso)
    if request.method == 'POST':
        try:
            nivel, anio, comision, turno, cupo = _datos_curso(request)
            if Curso.objects.filter(
                nivel_educativo=nivel, anio=anio, comision__iexact=comision, turno__iexact=turno
            ).exclude(id_curso=id_curso).exists():
                raise ValueError('Ya existe otro curso con ese nivel, año, comisión y turno.')
            curso.nivel_educativo = nivel
            curso.anio = anio
            curso.comision = comision
            curso.turno = turno
            curso.cupo_maximo = cupo
            curso.save()
            messages.success(request, 'Curso actualizado correctamente.')
        except (ValueError, IntegrityError) as error:
            messages.error(request, str(error))
    return redirect('lista-niveles-cursos-admin')


@never_cache
def baja_curso_admin(request, id_curso):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        curso = get_object_or_404(Curso, id_curso=id_curso)
        tiene_alumnos = Alumno.objects.filter(id_curso=curso).exists()
        tiene_materias = CursoCursaMaterias.objects.filter(id_curso=curso).exists()
        tiene_docentes = DocenteDictaMateria.objects.filter(id_curso=curso).exists()
        if tiene_alumnos or tiene_materias or tiene_docentes:
            messages.error(request, 'No se puede eliminar el curso porque tiene alumnos, materias o profesores asociados.')
        else:
            curso.delete()
            messages.success(request, 'Curso eliminado correctamente.')
    return redirect('lista-niveles-cursos-admin')


def _datos_materia(request):
    nombre = (request.POST.get('nombre') or '').strip()
    descripcion = (request.POST.get('descripcion') or '').strip()
    carga_raw = request.POST.get('carga_horaria') or ''
    clases_raw = request.POST.get('cantidad_clases') or ''
    if not nombre:
        raise ValueError('El nombre de la materia es obligatorio.')
    try:
        carga_horaria = int(carga_raw)
        cantidad_clases = int(clases_raw)
    except (TypeError, ValueError):
        raise ValueError('La carga horaria y la cantidad de clases deben ser números.')
    if carga_horaria <= 0 or cantidad_clases <= 0:
        raise ValueError('La carga horaria y la cantidad de clases deben ser mayores que cero.')
    cursos = []
    for curso_id in request.POST.getlist('cursos'):
        try:
            cursos.append(int(curso_id))
        except (TypeError, ValueError):
            continue
    return nombre, descripcion, carga_horaria, cantidad_clases, list(dict.fromkeys(cursos))


@never_cache
def alta_materia_admin(request):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        try:
            nombre, descripcion, carga_horaria, cantidad_clases, cursos = _datos_materia(request)
            if Materia.objects.filter(nombre__iexact=nombre).exists():
                raise ValueError('Ya existe una materia con ese nombre.')
            with transaction.atomic():
                materia = Materia.objects.create(
                    nombre=nombre,
                    descripcion=descripcion,
                    carga_horaria=carga_horaria,
                    cantidad_clases=cantidad_clases,
                )
                CursoCursaMaterias.objects.bulk_create([
                    CursoCursaMaterias(id_curso_id=curso_id, id_materia=materia)
                    for curso_id in cursos
                    if Curso.objects.filter(id_curso=curso_id).exists()
                ])
            messages.success(request, 'Materia creada correctamente.')
        except (ValueError, IntegrityError) as error:
            messages.error(request, str(error))
    return redirect('lista-materias-admin')


@never_cache
def modificar_materia_admin(request, id_materia):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    materia = get_object_or_404(Materia, id_materia=id_materia)
    if request.method == 'POST':
        try:
            nombre, descripcion, carga_horaria, cantidad_clases, cursos = _datos_materia(request)
            if Materia.objects.filter(nombre__iexact=nombre).exclude(id_materia=id_materia).exists():
                raise ValueError('Ya existe otra materia con ese nombre.')
            with transaction.atomic():
                materia.nombre = nombre
                materia.descripcion = descripcion
                materia.carga_horaria = carga_horaria
                materia.cantidad_clases = cantidad_clases
                materia.save()
                CursoCursaMaterias.objects.filter(id_materia=materia).delete()
                CursoCursaMaterias.objects.bulk_create([
                    CursoCursaMaterias(id_curso_id=curso_id, id_materia=materia)
                    for curso_id in cursos
                    if Curso.objects.filter(id_curso=curso_id).exists()
                ])
            messages.success(request, 'Materia actualizada correctamente.')
        except (ValueError, IntegrityError) as error:
            messages.error(request, str(error))
    return redirect('lista-materias-admin')


@never_cache
def baja_materia_admin(request, id_materia):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        materia = get_object_or_404(Materia, id_materia=id_materia)
        tiene_dependencias = (
            CursoCursaMaterias.objects.filter(id_materia=materia).exists()
            or DocenteDictaMateria.objects.filter(id_materia=materia).exists()
            or Calificacion.objects.filter(id_materia=materia).exists()
            or Tarea.objects.filter(materia=materia).exists()
        )
        if tiene_dependencias:
            messages.error(request, 'No se puede eliminar la materia porque tiene cursos, profesores o actividades asociadas.')
        else:
            materia.delete()
            messages.success(request, 'Materia eliminada correctamente.')
    return redirect('lista-materias-admin')


@never_cache
def lista_deportes_admin(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona or dashboard_url != 'dashboard-administrativo':
        return redirect('login')
    request.session['panel_activo'] = 'deportes-admin'
    return redirect('dashboard-administrativo')


def _hora_formulario(valor):
    try:
        return datetime.strptime(valor or '', '%H:%M').time()
    except (TypeError, ValueError):
        raise ValueError('Las horas deben tener el formato HH:MM.')


def _horarios_superpuestos(queryset, dia, inicio, fin, excluir=None):
    for horario in queryset:
        if excluir is not None and horario.id_horario == excluir:
            continue
        if horario.dia_semana.strip().lower() == dia.strip().lower() and max(horario.hora_inicio, inicio) < min(horario.hora_fin, fin):
            return horario
    return None


@never_cache
def alta_deporte_admin(request):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        instalacion_id = request.POST.get('id_instalacion')
        if not nombre or not instalacion_id:
            messages.error(request, 'El nombre y la instalación son obligatorios.')
        elif DisciplinaDeportiva.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, 'Ya existe ese deporte.')
        else:
            instalacion = get_object_or_404(Instalacion, id=instalacion_id)
            DisciplinaDeportiva.objects.create(nombre=nombre, id_instalacion=instalacion)
            messages.success(request, 'Deporte creado correctamente.')
    return redirect('lista-deportes-admin')


@never_cache
def modificar_deporte_admin(request, id_disciplina):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    deporte = get_object_or_404(DisciplinaDeportiva, id_disciplina=id_disciplina)
    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        instalacion_id = request.POST.get('id_instalacion')
        if not nombre or not instalacion_id:
            messages.error(request, 'El nombre y la instalación son obligatorios.')
        elif DisciplinaDeportiva.objects.filter(nombre__iexact=nombre).exclude(id_disciplina=id_disciplina).exists():
            messages.error(request, 'Ya existe otro deporte con ese nombre.')
        else:
            deporte.nombre = nombre
            deporte.id_instalacion_id = instalacion_id
            deporte.save(update_fields=['nombre', 'id_instalacion'])
            messages.success(request, 'Deporte actualizado correctamente.')
    return redirect('lista-deportes-admin')


@never_cache
def baja_deporte_admin(request, id_disciplina):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        deporte = get_object_or_404(DisciplinaDeportiva, id_disciplina=id_disciplina)
        if deporte.grupos.exists() or Alumno.objects.filter(id_disciplina=deporte).exists():
            messages.error(request, 'No se puede eliminar el deporte porque tiene grupos o alumnos asociados.')
        else:
            deporte.delete()
            messages.success(request, 'Deporte eliminado correctamente.')
    return redirect('lista-deportes-admin')


def _datos_grupo_deportivo(request):
    deporte_id = request.POST.get('id_disciplina')
    nivel_id = request.POST.get('nivel_educativo')
    profesor_id = request.POST.get('profesor_responsable')
    dia = (request.POST.get('dia_semana') or '').strip()
    turno = (request.POST.get('turno') or '').strip()
    inicio = _hora_formulario(request.POST.get('hora_inicio'))
    fin = _hora_formulario(request.POST.get('hora_fin'))
    cupo_raw = request.POST.get('cupo_maximo') or ''
    if not deporte_id or not nivel_id or not profesor_id or not dia or not turno:
        raise ValueError('Deporte, nivel, profesor, día, turno y horario son obligatorios.')
    if inicio >= fin:
        raise ValueError('La hora de finalización debe ser posterior a la de inicio.')
    cupo = int(cupo_raw) if cupo_raw else None
    if cupo is not None and cupo <= 0:
        raise ValueError('El cupo debe ser mayor que cero.')
    return deporte_id, nivel_id, profesor_id, dia, turno, inicio, fin, cupo


@never_cache
def alta_grupo_deportivo_admin(request):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        try:
            deporte_id, nivel_id, profesor_id, dia, turno, inicio, fin, cupo = _datos_grupo_deportivo(request)
            if GrupoDeportivo.objects.filter(id_disciplina_id=deporte_id, nivel_educativo_id=nivel_id, dia_semana=dia, turno=turno, hora_inicio=inicio, hora_fin=fin).exists():
                raise ValueError('Ya existe un grupo con ese deporte, nivel y horario.')
            grupo = GrupoDeportivo.objects.create(
                id_disciplina_id=deporte_id, nivel_educativo_id=nivel_id,
                profesor_responsable_id=profesor_id, dia_semana=dia,
                turno=turno, hora_inicio=inicio, hora_fin=fin, cupo_maximo=cupo,
            )
            Horario.objects.create(grupo_deportivo=grupo, dia_semana=dia, hora_inicio=inicio, hora_fin=fin)
            messages.success(request, 'Grupo deportivo creado correctamente.')
        except (ValueError, IntegrityError) as error:
            messages.error(request, str(error))
    return redirect('lista-deportes-admin')


@never_cache
def modificar_grupo_deportivo_admin(request, id_grupo):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    grupo = get_object_or_404(GrupoDeportivo, id_grupo=id_grupo)
    if request.method == 'POST':
        try:
            datos = _datos_grupo_deportivo(request)
            deporte_id, nivel_id, profesor_id, dia, turno, inicio, fin, cupo = datos
            if GrupoDeportivo.objects.filter(id_disciplina_id=deporte_id, nivel_educativo_id=nivel_id, dia_semana=dia, turno=turno, hora_inicio=inicio, hora_fin=fin).exclude(id_grupo=id_grupo).exists():
                raise ValueError('Ya existe otro grupo con ese deporte, nivel y horario.')
            grupo.id_disciplina_id, grupo.nivel_educativo_id = deporte_id, nivel_id
            grupo.profesor_responsable_id, grupo.dia_semana, grupo.turno = profesor_id, dia, turno
            grupo.hora_inicio, grupo.hora_fin, grupo.cupo_maximo = inicio, fin, cupo
            grupo.save()
            Horario.objects.update_or_create(
                grupo_deportivo=grupo,
                defaults={'dia_semana': dia, 'hora_inicio': inicio, 'hora_fin': fin},
            )
            messages.success(request, 'Grupo deportivo actualizado correctamente.')
        except (ValueError, IntegrityError) as error:
            messages.error(request, str(error))
    return redirect('lista-deportes-admin')


@never_cache
def baja_grupo_deportivo_admin(request, id_grupo):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        grupo = get_object_or_404(GrupoDeportivo, id_grupo=id_grupo)
        if grupo.inscripciones.filter(estado='Activa').exists():
            messages.error(request, 'No se puede eliminar un grupo con alumnos inscriptos.')
        else:
            grupo.delete()
            messages.success(request, 'Grupo deportivo eliminado correctamente.')
    return redirect('lista-deportes-admin')


@never_cache
def lista_horarios_admin(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona or dashboard_url != 'dashboard-administrativo':
        return redirect('login')
    request.session['panel_activo'] = 'horarios-admin'
    return redirect('dashboard-administrativo')


def _datos_horario_admin(request):
    tipo = request.POST.get('tipo')
    dia = (request.POST.get('dia_semana') or '').strip().lower()
    inicio = _hora_formulario(request.POST.get('hora_inicio'))
    fin = _hora_formulario(request.POST.get('hora_fin'))
    if tipo not in ('academico', 'deportivo') or not dia:
        raise ValueError('Tipo y día son obligatorios.')
    if inicio >= fin:
        raise ValueError('La hora de finalización debe ser posterior a la de inicio.')
    return tipo, dia, inicio, fin


@never_cache
def alta_horario_admin(request):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        try:
            tipo, dia, inicio, fin = _datos_horario_admin(request)
            if tipo == 'academico':
                relacion = get_object_or_404(CursoCursaMaterias, id=request.POST.get('curso_materia'))
                existentes = Horario.objects.filter(curso_materia__id_curso=relacion.id_curso)
                if _horarios_superpuestos(existentes, dia, inicio, fin):
                    raise ValueError('El curso ya tiene otra actividad en ese horario.')
                Horario.objects.create(curso_materia=relacion, dia_semana=dia, hora_inicio=inicio, hora_fin=fin)
            else:
                grupo = get_object_or_404(GrupoDeportivo, id_grupo=request.POST.get('grupo_deportivo'))
                existentes = Horario.objects.filter(grupo_deportivo__nivel_educativo=grupo.nivel_educativo)
                if _horarios_superpuestos(existentes, dia, inicio, fin):
                    raise ValueError('Ya existe una actividad deportiva superpuesta para ese nivel.')
                Horario.objects.create(grupo_deportivo=grupo, dia_semana=dia, hora_inicio=inicio, hora_fin=fin)
            messages.success(request, 'Horario creado correctamente.')
        except (ValueError, IntegrityError) as error:
            messages.error(request, str(error))
    return redirect('lista-horarios-admin')


@never_cache
def modificar_horario_admin(request, id_horario):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    horario = get_object_or_404(Horario, id_horario=id_horario)
    if request.method == 'POST':
        try:
            tipo, dia, inicio, fin = _datos_horario_admin(request)
            if tipo == 'academico':
                relacion = get_object_or_404(CursoCursaMaterias, id=request.POST.get('curso_materia'))
                existentes = Horario.objects.filter(curso_materia__id_curso=relacion.id_curso)
                horario.curso_materia, horario.grupo_deportivo = relacion, None
            else:
                grupo = get_object_or_404(GrupoDeportivo, id_grupo=request.POST.get('grupo_deportivo'))
                existentes = Horario.objects.filter(grupo_deportivo__nivel_educativo=grupo.nivel_educativo)
                horario.grupo_deportivo, horario.curso_materia = grupo, None
            if _horarios_superpuestos(existentes, dia, inicio, fin, excluir=horario.id_horario):
                raise ValueError('El nuevo horario se superpone con otra actividad.')
            horario.dia_semana, horario.hora_inicio, horario.hora_fin = dia, inicio, fin
            horario.save()
            if horario.grupo_deportivo_id:
                grupo = horario.grupo_deportivo
                grupo.dia_semana, grupo.hora_inicio, grupo.hora_fin = dia, inicio, fin
                grupo.save(update_fields=['dia_semana', 'hora_inicio', 'hora_fin'])
            messages.success(request, 'Horario actualizado correctamente.')
        except (ValueError, IntegrityError) as error:
            messages.error(request, str(error))
    return redirect('lista-horarios-admin')


@never_cache
def baja_horario_admin(request, id_horario):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        get_object_or_404(Horario, id_horario=id_horario).delete()
        messages.success(request, 'Horario eliminado correctamente.')
    return redirect('lista-horarios-admin')


@never_cache
def alta_inscripcion_deportiva_admin(request):
    if not _validar_acceso_niveles(request):
        return redirect('login')
    if request.method == 'POST':
        try:
            alumno = get_object_or_404(Alumno, legajo=request.POST.get('legajo_alumno'))
            alumno = Alumno.objects.select_related('id_curso').get(legajo=alumno.legajo)
            grupo = get_object_or_404(GrupoDeportivo.objects.select_related('id_disciplina', 'nivel_educativo'), id_grupo=request.POST.get('id_grupo'), estado='Activo')
            if alumno.id_curso_id is None or alumno.id_curso.nivel_educativo_id != grupo.nivel_educativo_id:
                raise ValueError('El grupo deportivo no corresponde al nivel del alumno.')
            if (alumno.id_curso.turno or '').strip().lower() == grupo.turno.strip().lower():
                raise ValueError('El deporte debe estar en el turno contrario al curso del alumno.')
            actuales = list(InscripcionDeportiva.objects.filter(id_alumno=alumno, estado='Activa').select_related('id_grupo', 'id_grupo__id_disciplina'))
            if len(actuales) >= 2:
                raise ValueError('El alumno ya tiene el máximo de dos deportes.')
            if any(i.id_grupo_id == grupo.id_grupo for i in actuales):
                raise ValueError('El alumno ya está inscripto en ese grupo.')
            if grupo.cupo_maximo and grupo.inscripciones.filter(estado='Activa').count() >= grupo.cupo_maximo:
                raise ValueError('El grupo ya alcanzó su cupo máximo.')
            conflicto = _grupos_deportivos_en_conflicto(grupo, actuales)
            if conflicto:
                raise ValueError(f'El horario se superpone con {conflicto.id_grupo.id_disciplina.nombre}.')
            InscripcionDeportiva.objects.create(id_alumno=alumno, id_grupo=grupo)
            messages.success(request, 'Alumno inscripto en el deporte correctamente.')
        except (ValueError, IntegrityError) as error:
            messages.error(request, str(error))
    return redirect('lista-deportes-admin')

@never_cache
def lista_profesores_admin(request):
    """Vista para mostrar el panel de profesores dentro del dashboard administrativo."""
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona or dashboard_url != 'dashboard-administrativo':
        return redirect('login')
    
    request.session['panel_activo'] = 'profesores'
    
    # Datos básicos del dashboard (para que no rompa la plantilla)
    administrativo = PersonalAdministrativo.objects.filter(id_persona=persona).first()
    instalaciones = Instalacion.objects.all()
    reservas = Reserva.objects.select_related('id_instalacion', 'id_persona_solicitante').all()
    
    if os.path.exists(OPINIONES_FILE):
        with open(OPINIONES_FILE, 'r', encoding='utf-8') as f:
            opiniones = json.load(f)
    else:
        opiniones = []
    
    cuotas_pendientes = PagoPendiente.objects.exclude(estado='Pagada').count()
    solicitudes = SolicitudInscripcion.objects.all().order_by('-fecha_solicitud')
    inscripciones_pendientes = SolicitudInscripcion.objects.filter(estado="Pendiente").count()
    pagos_pendientes = PagoPendiente.objects.all()
    documentacion_pendiente = DocumentacionAlumno.objects.filter(estado='Pendiente').count()
    documentaciones = DocumentacionAlumno.objects.filter(estado='Pendiente').order_by('-fecha_envio')
    
    # DATOS DE PROFESORES
    profesores = Docente.objects.select_related('id_persona').all().order_by('id_persona__apellido', 'id_persona__nombre')
    curso_materia_options = CursoCursaMaterias.objects.select_related(
        'id_curso', 'id_materia'
    ).order_by('id_curso__nivel_educativo__nombre', 'id_curso__anio', 'id_curso__comision', 'id_materia__nombre')
    for opcion in curso_materia_options:
        opcion.clave = f'{opcion.id_curso_id}:{opcion.id_materia_id}'
    materia_curso_options = []
    for materia in Materia.objects.all().order_by('nombre'):
        materia.cursos_disponibles = Curso.objects.filter(
            cursocursamaterias__id_materia=materia
        ).distinct().order_by('nivel_educativo__nombre', 'anio', 'comision')
        for curso in materia.cursos_disponibles:
            curso.asignacion_clave = f'{curso.id_curso}:{materia.id_materia}'
        if materia.cursos_disponibles.exists():
            materia_curso_options.append(materia)
    for profesor in profesores:
        relaciones = DocenteDictaMateria.objects.filter(
            id_docente=profesor
        ).select_related('id_materia')
        profesor.materia_ids = [relacion.id_materia_id for relacion in relaciones]
        relaciones_directas = [relacion for relacion in relaciones if relacion.id_curso_id]
        if relaciones_directas:
            profesor.asignacion_keys = [
                f'{relacion.id_curso_id}:{relacion.id_materia_id}'
                for relacion in relaciones_directas
            ]
        else:
            profesor.asignacion_keys = [
                opcion.clave for opcion in curso_materia_options
                if opcion.id_materia_id in profesor.materia_ids
            ]
    
    # Si viene un legajo por GET, mostrar detalle
    legajo_detalle = request.GET.get('legajo')
    profesor_detalle = None
    if legajo_detalle:
        profesor_detalle = get_object_or_404(
            Docente.objects.select_related('id_persona'), 
            legajo=legajo_detalle
        )
        profesor_detalle.asignaciones = DocenteDictaMateria.objects.filter(
            id_docente=profesor_detalle,
            id_curso__isnull=False,
        ).select_related('id_curso', 'id_materia').order_by(
            'id_curso__nivel_educativo__nombre', 'id_curso__anio', 'id_curso__comision', 'id_materia__nombre'
        )
    
    return render(request, 'core/dashboard-administrativo.html', {
        'persona': persona,
        'administrativo': administrativo,
        'instalaciones': instalaciones,
        'reservas': reservas,
        'opiniones': opiniones,
        'cuotas_pendientes': cuotas_pendientes,
        'solicitudes': solicitudes,
        'inscripciones_pendientes': inscripciones_pendientes,
        'pagos_pendientes': pagos_pendientes,
        'documentaciones': documentaciones,
        'documentacion_pendiente': documentacion_pendiente,
        'panel_activo': 'profesores',
        'profesores': profesores,
        'curso_materia_options': curso_materia_options,
        'materia_curso_options': materia_curso_options,
        'profesor_detalle': profesor_detalle,
    })

@never_cache
def detalle_profesor_admin(request, legajo):
    """Redirige a la lista de profesores pasando el legajo por GET para mostrar el detalle."""
    return redirect(f"{reverse('lista-profesores-admin')}?legajo={legajo}")


def _asignaciones_profesor(post):
    """Devuelve pares (curso, materia) que existen en el plan del curso."""
    pares = []
    for valor in post.getlist('asignaciones'):
        try:
            curso_id, materia_id = valor.split(':', 1)
            curso_id = int(curso_id)
            materia_id = int(materia_id)
        except (TypeError, ValueError):
            continue
        if CursoCursaMaterias.objects.filter(
            id_curso_id=curso_id,
            id_materia_id=materia_id,
        ).exists():
            pares.append((curso_id, materia_id))
    return list(dict.fromkeys(pares))


@never_cache
def alta_profesor_admin(request):
    """Registra la cuenta, los datos personales y el legajo de un docente."""
    persona_sesion, dashboard_url = obtener_datos_sesion(request)
    if not persona_sesion or dashboard_url != 'dashboard-administrativo':
        return redirect('login')

    if request.method == 'POST':
        nombre_usuario = (request.POST.get('nombre_usuario') or '').strip()
        contrasenia = request.POST.get('contrasenia') or ''
        dni = (request.POST.get('dni') or '').strip()
        nombre = (request.POST.get('nombre') or '').strip()
        apellido = (request.POST.get('apellido') or '').strip()
        fecha_nacimiento = request.POST.get('fecha_nacimiento') or ''
        direccion = (request.POST.get('direccion') or '').strip()
        telefono = (request.POST.get('telefono') or '').strip()
        email = (request.POST.get('email') or '').strip() or None
        titulo = (request.POST.get('titulo') or '').strip()
        especialidad = (request.POST.get('especialidad') or '').strip() or None
        fecha_ingreso = request.POST.get('fecha_ingreso') or ''
        asignaciones = _asignaciones_profesor(request.POST)
        errores = []

        if not nombre_usuario or not contrasenia:
            errores.append('El usuario y la contraseña provisoria son obligatorios.')
        if not dni or not nombre or not apellido:
            errores.append('DNI, nombre y apellido son obligatorios.')
        if Usuario.objects.filter(nombre_usuario=nombre_usuario).exists():
            errores.append('El nombre de usuario ya existe.')
        if dni and Persona.objects.filter(dni=dni).exists():
            errores.append('El DNI ya está registrado.')
        if email and Usuario.objects.filter(correo=email).exists():
            errores.append('El correo ya está asociado a otra cuenta.')
        if not titulo:
            errores.append('El título docente es obligatorio.')

        try:
            fecha_nac_obj = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            fecha_nac_obj = None
            errores.append('La fecha de nacimiento no es válida.')
        try:
            fecha_ingreso_obj = datetime.strptime(fecha_ingreso, '%Y-%m-%d').date() if fecha_ingreso else date.today()
        except (ValueError, TypeError):
            fecha_ingreso_obj = None
            errores.append('La fecha de ingreso no es válida.')

        if errores:
            for error in errores:
                messages.error(request, error)
            return redirect('lista-profesores-admin')

        with transaction.atomic():
            usuario = Usuario.objects.create(
                nombre_usuario=nombre_usuario,
                contrasenia=contrasenia,
                correo=email,
            )
            persona = Persona.objects.create(
                id_usuario=usuario,
                dni=dni,
                nombre=nombre,
                apellido=apellido,
                fecha_nacimiento=fecha_nac_obj,
                direccion=direccion or None,
                telefono=telefono or None,
                email=email,
            )
            docente = Docente.objects.create(
                id_persona=persona,
                titulo=titulo,
                especialidad=especialidad,
                fecha_ingreso=fecha_ingreso_obj,
            )
            DocenteDictaMateria.objects.bulk_create([
                DocenteDictaMateria(
                    id_docente=docente,
                    id_curso_id=curso_id,
                    id_materia_id=materia_id,
                )
                for curso_id, materia_id in asignaciones
            ])
        messages.success(request, 'Profesor registrado correctamente.')

    return redirect('lista-profesores-admin')


@never_cache
def modificar_profesor_admin(request, legajo):
    persona_sesion, dashboard_url = obtener_datos_sesion(request)
    if not persona_sesion or dashboard_url != 'dashboard-administrativo':
        return redirect('login')

    profesor = get_object_or_404(Docente.objects.select_related('id_persona', 'id_persona__id_usuario'), legajo=legajo)
    persona = profesor.id_persona
    if request.method == 'POST':
        dni = (request.POST.get('dni') or '').strip()
        email = (request.POST.get('email') or '').strip() or None
        try:
            fecha_nac_obj = datetime.strptime(request.POST.get('fecha_nacimiento') or '', '%Y-%m-%d').date()
            fecha_ingreso_obj = datetime.strptime(request.POST.get('fecha_ingreso') or '', '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Las fechas ingresadas no son válidas.')
            return redirect('lista-profesores-admin')

        errores = []
        if not dni or not (request.POST.get('nombre') or '').strip() or not (request.POST.get('apellido') or '').strip():
            errores.append('DNI, nombre y apellido son obligatorios.')
        if Persona.objects.filter(dni=dni).exclude(id=persona.id).exists():
            errores.append('El DNI ya está registrado en otra persona.')
        if email and Usuario.objects.filter(correo=email).exclude(id=persona.id_usuario_id).exists():
            errores.append('El correo ya está asociado a otra cuenta.')
        if not (request.POST.get('titulo') or '').strip():
            errores.append('El título docente es obligatorio.')
        if errores:
            for error in errores:
                messages.error(request, error)
            return redirect('lista-profesores-admin')

        with transaction.atomic():
            persona.dni = dni
            persona.nombre = (request.POST.get('nombre') or '').strip()
            persona.apellido = (request.POST.get('apellido') or '').strip()
            persona.fecha_nacimiento = fecha_nac_obj
            persona.direccion = (request.POST.get('direccion') or '').strip() or None
            persona.telefono = (request.POST.get('telefono') or '').strip() or None
            persona.email = email
            persona.save()
            if persona.id_usuario:
                persona.id_usuario.correo = email
                persona.id_usuario.save(update_fields=['correo'])
            profesor.titulo = (request.POST.get('titulo') or '').strip()
            profesor.especialidad = (request.POST.get('especialidad') or '').strip() or None
            profesor.fecha_ingreso = fecha_ingreso_obj
            profesor.save()
            DocenteDictaMateria.objects.filter(id_docente=profesor).delete()
            asignaciones = _asignaciones_profesor(request.POST)
            DocenteDictaMateria.objects.bulk_create([
                DocenteDictaMateria(
                    id_docente=profesor,
                    id_curso_id=curso_id,
                    id_materia_id=materia_id,
                )
                for curso_id, materia_id in asignaciones
            ])
        messages.success(request, 'Datos del profesor actualizados correctamente.')

    return redirect('lista-profesores-admin')


@never_cache
def baja_profesor_admin(request, legajo):
    persona_sesion, dashboard_url = obtener_datos_sesion(request)
    if not persona_sesion or dashboard_url != 'dashboard-administrativo':
        return redirect('login')

    if request.method == 'POST':
        profesor = get_object_or_404(Docente.objects.select_related('id_persona'), legajo=legajo)
        if profesor.grupos_deportivos.exists():
            messages.error(request, 'No se puede dar de baja al profesor porque es responsable de grupos deportivos.')
            return redirect('lista-profesores-admin')
        persona = profesor.id_persona
        usuario = persona.id_usuario
        with transaction.atomic():
            DocenteDictaMateria.objects.filter(id_docente=profesor).delete()
            DocenteDisciplina.objects.filter(legajo_docente=profesor).delete()
            profesor.delete()
            persona.delete()
            if usuario:
                usuario.delete()
        messages.success(request, 'Profesor dado de baja correctamente.')

    return redirect('lista-profesores-admin')

@never_cache
def aprobar_inscripcion(request, id_solicitud):

    solicitud = SolicitudInscripcion.objects.get(
        id_solicitud=id_solicitud
    )

    persona_alumno = Persona.objects.create(
        dni=solicitud.dni_alumno,
        nombre=solicitud.nombre_alumno,
        apellido=solicitud.apellido_alumno,
        fecha_nacimiento=solicitud.fecha_nacimiento,
        direccion=solicitud.direccion,
        telefono=solicitud.telefono_alumno or solicitud.telefono,
        email=solicitud.email_alumno or solicitud.email
    )

    persona_tutor = Persona.objects.create(
        dni=solicitud.dni_tutor,
        nombre=solicitud.nombre_tutor,
        apellido=solicitud.apellido_tutor,
        fecha_nacimiento=date(2000, 1, 1),
        telefono=solicitud.telefono,
        email=solicitud.email,
        direccion=solicitud.direccion_tutor,
    )

    tutor = Tutor.objects.create(
        id_persona=persona_tutor,
        telefono_contacto=solicitud.telefono,
        email_contacto=solicitud.email
    )
    
    hoy = date.today()

    edad = (
        hoy.year
        - solicitud.fecha_nacimiento.year
        - (
            (hoy.month, hoy.day)
            <
            (
                solicitud.fecha_nacimiento.month,
                solicitud.fecha_nacimiento.day
            )
        )
    )

    nivel_solicitud = solicitud.nivel.strip().lower()
    nivel_nombre = {
        'inicial': 'Inicial',
        'primaria': 'Primario',
        'primario': 'Primario',
        'secundaria': 'Secundario',
        'secundario': 'Secundario',
    }.get(nivel_solicitud, solicitud.nivel.strip())

    if nivel_solicitud in ('primaria', 'primario'):
        anio = max(1, min(7, edad - 5))
    else:
        anio = max(1, min(5, edad - 12))

    curso = Curso.objects.filter(
        nivel_educativo__nombre__iexact=nivel_nombre,
        turno__iexact=solicitud.turno,
        anio=anio
    ).order_by('comision').first()

    if not curso:
        solicitud.estado = 'Error'
        solicitud.save()

        return redirect('dashboard-administrativo')

    alumno = Alumno.objects.create(
        id_persona=persona_alumno,
        fecha_ingreso=date.today(),
        id_curso=curso
    )

    TutorTutoraAlumno.objects.create(
        id_tutor=tutor,
        id_alumno=alumno,
        tipo_parentesco=solicitud.parentesco,
    )

    Inscripcion.objects.create(
        fecha_inscripcion=date.today(),
        estado='Activa',
        id_curso=curso,
        legajo_alumno=alumno
    )

    solicitud.delete()

    return redirect('dashboard-administrativo')

@never_cache
def rechazar_inscripcion(request, id_solicitud):

    solicitud = get_object_or_404(
        SolicitudInscripcion,
        id_solicitud=id_solicitud
    )

    solicitud.delete()

    return redirect('dashboard-administrativo')

@never_cache
def crear_reserva(request):
    print(request.POST)

    if request.method == "POST":

        id_instalacion = request.POST.get("espacio")
        fecha = request.POST.get("fecha")
        responsable = request.POST.get("responsable")
        
        horario = request.POST.get("horario", "").strip()

        if "-" not in horario:
            messages.error(request, "Debe escribir un horario válido.", extra_tags="reservas")
            return redirect(reverse('dashboard-administrativo') + '#reservas')

        hora_inicio, hora_fin = horario.split("-", 1)

        
        try:
            instalacion = Instalacion.objects.get(pk=id_instalacion)
        except Instalacion.DoesNotExist:
            messages.error(request, "Debe seleccionar un espacio válido.", extra_tags="reservas")
            return redirect(reverse('dashboard-administrativo') + '#reservas')

        partes = responsable.strip().split()

        if len(partes) < 2:
            messages.error(
                request,
                "Debe ingresar el nombre y apellido del solicitante. Ejemplo: Juan Ramírez.",
                extra_tags="reservas"
            )
            return redirect(reverse('dashboard-administrativo') + '#reservas')

        nombre = partes[0]
        apellido = partes[1]

        persona = Persona.objects.filter(
            nombre__iexact=nombre,
            apellido__iexact=apellido
        ).first()

        if not persona:
            messages.error(
                request,
                "No se encontró una persona con ese nombre y apellido.",
                extra_tags="reservas"
            )
            return redirect(reverse('dashboard-administrativo') + '#reservas')

        administrativo = PersonalAdministrativo.objects.first()
        
        try:
            hora_inicio = datetime.strptime(hora_inicio.strip(), "%H:%M").time()
            hora_fin = datetime.strptime(hora_fin.strip(), "%H:%M").time()
        except ValueError:
            messages.error(request, "El horario ingresado no es válido.", extra_tags="reservas")
            return redirect(reverse('dashboard-administrativo') + '#reservas')
        
        fecha = request.POST.get("fecha")
        

        try:
            fecha = datetime.strptime(fecha, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            messages.error(request, "La fecha ingresada no es válida.", extra_tags="reservas")
            return redirect(reverse('dashboard-administrativo') + '#reservas')

        if fecha < date.today():
            messages.error(request, "No se pueden registrar reservas para días anteriores.", extra_tags="reservas")
            return redirect(reverse('dashboard-administrativo') + '#reservas')
        
        if Reserva.objects.filter(
            id_instalacion=instalacion,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin
        ).exists():
            messages.error(
                request,
                "Ya existe una reserva para ese espacio, fecha y horario.",
                extra_tags="reservas"
            )
            return redirect(reverse('dashboard-administrativo') + '#reservas')


        Reserva.objects.create(
            nombre=f"Reserva {instalacion.nombre}",
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            legajo_personal_evaluador=administrativo,
            id_persona_solicitante=persona,
            id_instalacion=instalacion
        )

        messages.success(request, "Reserva registrada correctamente.", extra_tags="reservas")
        return redirect(reverse('dashboard-administrativo') + '#reservas')

@never_cache
def eliminar_opinion(request, indice):

    if request.method == "POST":

        if os.path.exists(OPINIONES_FILE):

            with open(OPINIONES_FILE, 'r', encoding='utf-8') as f:
                opiniones = json.load(f)

            if 0 <= indice < len(opiniones):
                opiniones.pop(indice)

            with open(OPINIONES_FILE, 'w', encoding='utf-8') as f:
                json.dump(opiniones, f, ensure_ascii=False, indent=2)

    return redirect('dashboard-administrativo')

@never_cache
def crear_usuario(request):

    if request.method == "POST":

        dni = request.POST.get("dni")
        nombre_usuario = request.POST.get("nombre_usuario")
        contrasenia = request.POST.get("contrasenia")

        persona = Persona.objects.filter(
            dni=dni
        ).first()

        if not persona:
            messages.error(
                request,
                "No existe una persona con ese DNI.",
                extra_tags="usuarios"
            )
            request.session["panel_activo"] = "usuarios"
            return redirect("dashboard-administrativo")

        if persona.id_usuario:
            messages.error(
                request,
                "La persona ya tiene un usuario asignado.",
                extra_tags="usuarios"
            )
            request.session["panel_activo"] = "usuarios"
            return redirect("dashboard-administrativo")

        if Usuario.objects.filter(
            nombre_usuario=nombre_usuario
        ).exists():

            messages.error(
                request,
                "El nombre de usuario ya existe.",
                extra_tags="usuarios"
            )
            request.session["panel_activo"] = "usuarios"
            return redirect("dashboard-administrativo")
        
        correo = request.POST.get("correo")
        
        if Usuario.objects.filter(correo=correo).exists():
            messages.error(
                request,
                "Ese correo ya está registrado.",
                extra_tags="usuarios"
            )
            request.session["panel_activo"] = "usuarios"
            return redirect("dashboard-administrativo")

        usuario = Usuario.objects.create(
            nombre_usuario=nombre_usuario,
            contrasenia=contrasenia,
            correo=correo
        )

        persona.id_usuario = usuario
        persona.save()

        messages.success(
            request,
            "Usuario creado correctamente.",
            extra_tags="usuarios"
        )
        request.session["panel_activo"] = "usuarios"

    return redirect('dashboard-administrativo')

@never_cache
def dashboard_padres(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona:
        return redirect('login')
    if dashboard_url != 'dashboard-padres':
        return redirect(dashboard_url)

    tutor = Tutor.objects.filter(id_persona=persona).first()

    # 1. INICIALIZAR VARIABLES AQUÍ (fuera del if) para evitar UnboundLocalError
    hijos = []
    documentacion = None
    legajos_hijos = []  # <--- CLAVE: Se inicializa como lista vacía

    presentes = 0
    ausencias = 0
    tardanzas = 0
    suma_promedios = 0
    cantidad_promedios = 0

    if tutor:
        relaciones = TutorTutoraAlumno.objects.filter(
            id_tutor=tutor
        ).select_related(
            'id_alumno',
            'id_alumno__id_persona',
            'id_alumno__id_curso'
        )

        # 2. OBTENER LOS LEGAJOS DE LOS HIJOS ACTUALES
        legajos_hijos = list(relaciones.values_list('id_alumno', flat=True))

        for relacion in relaciones:
            alumno = relacion.id_alumno

            promedio = Calificacion.objects.filter(
                legajo_alumno=alumno
            ).aggregate(promedio=Avg('nota'))['promedio']

            promedio = float(promedio) if promedio else 0

            if promedio:
                suma_promedios += promedio
                cantidad_promedios += 1

            pres = Asistencia.objects.filter(legajo_alumno=alumno, tipo_asistencia='Presente').count()
            aus = Asistencia.objects.filter(legajo_alumno=alumno, tipo_asistencia='Ausente').count()
            tar = Asistencia.objects.filter(legajo_alumno=alumno, tipo_asistencia='Tardanza').count()

            presentes += pres
            ausencias += aus
            tardanzas += tar
            
            documentacion = DocumentacionAlumno.objects.filter(legajo_alumno=alumno).first()

            hijos.append({
                'alumno': alumno,
                'persona': alumno.id_persona,
                'curso': alumno.id_curso,
                'promedio': promedio,
                'presentes': pres,
                'ausencias': aus,
                'tardanzas': tar,
                'documentacion': documentacion,
            })

    # 📊 promedio general
    promedio_general = round(suma_promedios / cantidad_promedios, 2) if cantidad_promedios else 0
    total_asistencias = presentes + ausencias
    porcentaje_asistencia = round((presentes / total_asistencias) * 100, 0) if total_asistencias else 0

    COMUNICADOS_FILE = os.path.join(settings.BASE_DIR, "core", "comunicados.json")
    comunicados_filtrados = []
    vistos = set()

    def parse_fecha(c):
        try:
            return datetime.strptime(c.get("fecha", ""), '%d/%m/%Y %H:%M')
        except:
            return datetime.min

    if os.path.exists(COMUNICADOS_FILE):
        try:
            with open(COMUNICADOS_FILE, 'r', encoding='utf-8') as f:
                file_content = f.read().strip()
                comunicados = json.loads(file_content) if file_content else []

            if tutor: # Solo procesar si hay tutor
                for relacion in relaciones:
                    alumno = relacion.id_alumno
                    curso_alumno = f"{alumno.id_curso.nivel_educativo.nombre} {alumno.id_curso.anio}° {alumno.id_curso.comision}"

                    for c in comunicados:
                        clave = (c.get('titulo'), c.get('fecha'), c.get('rol'))
                        if clave in vistos:
                            continue

                        if c.get('rol') == 'Directivo':
                            comunicados_filtrados.append(c)
                            vistos.add(clave)
                        elif (c.get('rol') == 'Preceptor' and c.get('curso', '').strip().lower() == curso_alumno.strip().lower()):
                            comunicados_filtrados.append(c)
                            vistos.add(clave)

            comunicados_filtrados.sort(key=parse_fecha, reverse=True)
        except json.JSONDecodeError:
            comunicados_filtrados = []

    panel_activo = request.session.pop("panel_activo", "inicio")
    
    # 3. USAR legajos_hijos (que siempre existe, aunque esté vacío)
    cuotas_pendientes = Cuota.objects.filter(
        id_legajo_alumno__in=legajos_hijos,
        estado='Pendiente'
    ).count()

    cuotas = Cuota.objects.filter(
        id_legajo_alumno__in=legajos_hijos
    ).select_related(
        'id_legajo_alumno__id_persona'
    ).order_by('-id_cuota')
    
    return render(
        request,
        'core/dashboard-padres.html',
        {
            'persona': persona,
            'hijos': hijos,
            'promedio_general': promedio_general,
            'porcentaje_asistencia': porcentaje_asistencia,
            'presentes': presentes,
            'ausencias': ausencias,
            'tardanzas': tardanzas,
            'noticias': comunicados_filtrados,
            "panel_activo": panel_activo,
            'cuotas_pendientes': cuotas_pendientes,
            'cuotas': cuotas,
            'documentacion': documentacion,
        }
    )

@never_cache
def dashboard_preceptor(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona:
        return redirect('login')
    if dashboard_url != 'dashboard-preceptor':
        return redirect(dashboard_url)

    curso_id = request.POST.get('curso_id') or request.GET.get('curso_id')
    
    notificaciones = []

    preceptor = Preceptor.objects.filter(
        id_persona=persona
    ).first()

    cursos = Curso.objects.filter(
        legajo_preceptor=preceptor
    )

    curso_seleccionado = None

    if curso_id:
        curso_seleccionado = Curso.objects.filter(
            id_curso=curso_id,
            legajo_preceptor=preceptor
        ).first()

    if curso_seleccionado:
        alumnos = Alumno.objects.filter(
            id_curso=curso_seleccionado
        )

    else:
        alumnos = Alumno.objects.filter(
            id_curso=cursos.first()
        ) if cursos.exists() else []
        
    total_alumnos = 0
    hoy = date.today()

    asistencia_tomada = False

    if curso_seleccionado:
        asistencia_tomada = Asistencia.objects.filter(
            legajo_alumno__id_curso=curso_seleccionado,
            fecha=hoy
        ).exists()
    if request.method == 'POST' and not asistencia_tomada:

        fecha_hoy = date.today()

        Asistencia.objects.filter(
            fecha=fecha_hoy,
            legajo_alumno__in=alumnos
        ).delete()

        for alumno in alumnos:

            estado = request.POST.get(
                f'estado_{alumno.legajo}',
                'Presente'
            )

            observacion = request.POST.get(
                f'obs_{alumno.legajo}',
                ''
            )

            Asistencia.objects.create(
                legajo_alumno=alumno,
                fecha=fecha_hoy,
                tipo_asistencia=estado.capitalize(),
                observacion=observacion
            )
        return redirect('dashboard-preceptor') 
    total_alumnos = 0
    hoy = date.today()

    for curso in cursos:

        curso.asistencia_tomada = Asistencia.objects.filter(
            legajo_alumno__id_curso=curso,
            fecha=hoy
        ).exists()

        alumnos_curso = Alumno.objects.filter(
            id_curso=curso
        ).select_related('id_persona')

        for alumno in alumnos_curso:

            asistencia_hoy = Asistencia.objects.filter(
                legajo_alumno=alumno,
                fecha=hoy
            ).first()

            alumno.estado_hoy = (
                asistencia_hoy.tipo_asistencia
                if asistencia_hoy
                else "Sin registrar"
            )

        curso.alumnos = alumnos_curso
        curso.cantidad_alumnos = alumnos_curso.count()

        total_alumnos += curso.cantidad_alumnos

    presentes = Asistencia.objects.filter(
        fecha=hoy,
        tipo_asistencia='Presente'
    ).count()

    ausentes = Asistencia.objects.filter(
        fecha=hoy,
        tipo_asistencia='Ausente'
    ).count()

    tardanzas = Asistencia.objects.filter(
        fecha=hoy,
        tipo_asistencia='Tardanza'
    ).count()
    cursos_pendientes = []

    if os.path.exists(COMUNICADOS_FILE):

        try:

            with open(
                COMUNICADOS_FILE,
                'r',
                encoding='utf-8'
            ) as f:

                comunicados = json.load(f)

                contador = 0

                for comunicado in reversed(comunicados):

                    if comunicado.get('rol') == 'Directivo':

                        notificaciones.append({
                            'tipo': 'comunicado',
                            'icono': '📢',
                            'color': '#dbeafe',
                            'titulo': comunicado.get('titulo'),
                            'mensaje': comunicado.get('contenido'),
                            'fecha': comunicado.get('fecha')
                        })

                        contador += 1

                        if contador == 3:
                            break

        except Exception:
            pass
    for curso in cursos:

        curso.asistencia_tomada = Asistencia.objects.filter(
            legajo_alumno__id_curso=curso,
            fecha=hoy
        ).exists()

        if not curso.asistencia_tomada:
            cursos_pendientes.append(
                f"{curso.anio}° {curso.comision}"
            )

        alumnos_curso = Alumno.objects.filter(
            id_curso=curso
        ).select_related('id_persona')

    for curso in cursos_pendientes:

        notificaciones.append({
            'icono': '⚠️',
            'color': '#fef3c7',
            'titulo': 'Asistencia pendiente',
            'mensaje': (
                f'Falta registrar asistencia en el curso {curso}'
            )
        })
    justificaciones = Asistencia.objects.filter(
        legajo_alumno__id_curso__in=cursos,
        tipo_asistencia__in=['Ausente', 'Tardanza'],
        archivo_justificacion__isnull=False
    ).exclude(
        archivo_justificacion=''
    ).select_related(
        'legajo_alumno__id_persona',
        'legajo_alumno__id_curso'
    ).order_by('-fecha')

    for justificacion in justificaciones:
        ruta_completa = os.path.join(
            settings.MEDIA_ROOT,
            justificacion.archivo_justificacion
        )

        justificacion.archivo_existe = os.path.exists(
            ruta_completa
        )
        
    context = {
        'persona': persona,
        'cursos': cursos,
        'total_alumnos': total_alumnos,
        'alumnos': alumnos,
        'cantidad_cursos': cursos.count(),
        'presentes': presentes,
        'ausentes': ausentes,
        'tardanzas': tardanzas,
        'curso_seleccionado': curso_seleccionado,
        'noticias': Noticia.objects.order_by('-fecha_publicacion')[:5],
        'asistencia_tomada': asistencia_tomada,
        'cursos_pendientes': cursos_pendientes,
        'cantidad_pendientes': len(cursos_pendientes),
        'justificaciones': justificaciones,
        'notificaciones': notificaciones,
        'cantidad_notificaciones': len(notificaciones),
    }

    return render(
        request,
        'core/dashboard-preceptor.html',
        context
    )

def crear_noticia(request):

    if request.method == 'POST':

        titulo = request.POST.get('titulo')
        contenido = request.POST.get('contenido')
        imagen = request.FILES.get('imagen')

        persona = obtener_persona(request)

        administrativo = PersonalAdministrativo.objects.filter(
            id_persona=persona
        ).first()

        if len(contenido) > 350:
            return render(
                request,
                'core/dashboard-administrativo.html',
                {
                    'error': 'La noticia no puede superar los 350 caracteres.'
                }
            )

        ruta_imagen = None

        if imagen:

            if imagen:

                fs = FileSystemStorage(
                    location=os.path.join(settings.MEDIA_ROOT, 'noticias')
                )

                nombre_archivo = fs.save(
                    imagen.name,
                    imagen
                )

                ruta_imagen = f'noticias/{nombre_archivo}'

        Noticia.objects.create(
            titulo=titulo,
            contenido=contenido,
            fecha_publicacion=date.today(),
            legajo_personal=administrativo,
            imagen=ruta_imagen
        )
        return redirect('dashboard-administrativo')

    return redirect('dashboard-administrativo')
    
def guardar_opinion(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip() or 'Anónimo'
        opinion = request.POST.get('opinion', '').strip()

        # Validaciones básicas
        if not opinion:
            return render(request, 'core/contacto.html', {
                'error_opinion': 'La opinión no puede estar vacía.'
            })

        if len(opinion) > 500:
            return render(request, 'core/contacto.html', {
                'error_opinion': 'La opinión no puede superar los 500 caracteres.'
            })

        # Leer opiniones existentes
        if os.path.exists(OPINIONES_FILE) and os.path.getsize(OPINIONES_FILE) > 0:
            try:
                with open(OPINIONES_FILE, 'r', encoding='utf-8') as f:
                    opiniones = json.load(f)
            except json.JSONDecodeError:
                opiniones = []
        else:
            opiniones = []

        # Agregar la nueva opinión
        from datetime import datetime
        opiniones.append({
            'nombre': nombre,
            'texto': opinion,
            'fecha': datetime.now().strftime('%d/%m/%Y %H:%M')
        })

        # Guardar en el archivo
        with open(OPINIONES_FILE, 'w', encoding='utf-8') as f:
            json.dump(opiniones, f, ensure_ascii=False, indent=2)

        messages.success(
            request,
            "Tu opinión fue publicada correctamente. Desplazate hacia abajo para verla en la sección 'Opiniones de visitantes'."
        )

        return redirect('contacto')

def obtener_datos_sesion(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None, None
    try:
        usuario = Usuario.objects.get(id=usuario_id)
        persona = Persona.objects.filter(id_usuario=usuario).first()
        if not persona:
            return None, None
            
        # Determinar a que dashboard debe redirigir segun su rol
        dashboard_url = 'login'
        if PersonalAdministrativo.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-administrativo'
        elif Docente.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-docente'
        elif Tutor.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-padres'
        elif Preceptor.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-preceptor'
        elif Directivo.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-directivo'
        elif Alumno.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-alumno'
            
        return persona, dashboard_url
    except Usuario.DoesNotExist:
        return None, None

def logout(request):
    if 'usuario_id' in request.session:
        del request.session['usuario_id']
    return redirect('index')

def crear_comunicado(request):

    if request.method == 'POST':

        titulo = request.POST.get('titulo', '').strip()
        contenido_form = request.POST.get('contenido', '').strip()
        curso_id = request.POST.get('curso')

        persona = obtener_persona(request)

        rol = "Desconocido"

        if Directivo.objects.filter(id_persona=persona.id).exists():
            rol = "Directivo"
        elif Docente.objects.filter(id_persona=persona.id).exists():
            rol = "Docente"
        elif Preceptor.objects.filter(id_persona=persona.id).exists():
            rol = "Preceptor"
        elif PersonalAdministrativo.objects.filter(id_persona=persona.id).exists():
            rol = "Administrativo"

        if not titulo or not contenido_form:
            return redirect('dashboard-directivo')

        if len(contenido_form) > 500:
            return redirect('dashboard-directivo')

        comunicados = []

        if os.path.exists(COMUNICADOS_FILE):
            try:
                with open(COMUNICADOS_FILE, 'r', encoding='utf-8') as f:
                    file_content = f.read().strip()

                    if file_content:
                        comunicados = json.loads(file_content)

            except json.JSONDecodeError:
                comunicados = []

        # 👇 🔥 ACÁ VA LO NUEVO (ANTES DE ARMAR EL OBJETO)

        curso_obj = None

        if rol == "Preceptor" and curso_id:
            curso_obj = Curso.objects.filter(
                id_curso=curso_id,
                legajo_preceptor__id_persona=persona
            ).first()

        # 🔥 ARMADO DEL OBJETO (BASE)
        nuevo_comunicado = {
            'titulo': titulo,
            'contenido': contenido_form,
            'autor': f'{persona.nombre} {persona.apellido}',
            'rol': rol,
            'fecha': datetime.now().strftime('%d/%m/%Y %H:%M')
        }

        # 👇 SOLO SI ES PRECEPTOR
        if rol == "Preceptor" and curso_obj:
            nuevo_comunicado['curso_id'] = curso_obj.id_curso
            nuevo_comunicado['curso'] = f"{curso_obj.nivel_educativo.nombre} {curso_obj.anio}° {curso_obj.comision}"

        comunicados.append(nuevo_comunicado)

        with open(COMUNICADOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(
                comunicados,
                f,
                ensure_ascii=False,
                indent=2
            )

        if rol == "Preceptor":
            return redirect('dashboard-preceptor')
        elif rol == "Docente":
            return redirect('dashboard-docente')
        elif rol == "Administrativo":
            return redirect('dashboard-administrativo')
        else:
            return redirect('dashboard-directivo')
        
@never_cache
def registrar_pago(request):

    persona = obtener_persona(request)

    if not persona:
        return redirect('login')

    tutor = Tutor.objects.filter(
        id_persona=persona
    ).first()

    if request.method == 'POST':

        try:

            alumno = Alumno.objects.get(
                legajo=request.POST.get('alumno')
            )

            curso = alumno.id_curso

            arancel = Arancel.objects.get(
                nivel=curso.nivel_educativo.nombre
            )

            importe = arancel.monto

            if PagoPendiente.objects.filter(
                legajo_alumno=alumno,
                mes=request.POST.get('mes'),
                estado='Pendiente'
            ).exists():

                messages.error(
                    request,
                    'Ya existe una solicitud pendiente para ese mes.',
                    extra_tags="pagos"
                )

                request.session["panel_activo"] = "pagos"
                return redirect('dashboard-padres')

            if Cuota.objects.filter(
                id_legajo_alumno=alumno,
                periodo=request.POST.get('mes'),
                estado='Pagada'
            ).exists():

                messages.error(
                    request,
                    f'La cuota de {request.POST.get("mes")} ya fue abonada.',
                    extra_tags="pagos"
                )

                request.session["panel_activo"] = "pagos"
                return redirect('dashboard-padres')

            PagoPendiente.objects.create(
                id_tutor=tutor,
                legajo_alumno=alumno,
                mes=request.POST.get('mes'),
                importe=importe,
                estado='Pendiente',
                fecha_solicitud=timezone.now()
            )

            messages.success(
                request,
                'El comprobante de pago fue enviado correctamente y será revisado por administración.',
                extra_tags="pagos"
            )

        except Alumno.DoesNotExist:

            messages.error(
                request,
                'Debe seleccionar un alumno válido.',
                extra_tags="pagos"
            )

        except Arancel.DoesNotExist:

            messages.error(
                request,
                'No existe un arancel configurado para este nivel.',
                extra_tags="pagos"
            )

        except Exception as e:

            messages.error(
                request,
                f'Ocurrió un error al registrar el pago: {e}',
                extra_tags="pagos"
            )

        request.session["panel_activo"] = "pagos"
        return redirect('dashboard-padres')
    return redirect('dashboard-padres')

@never_cache
def aprobar_pago(request, id_pago):

    pago = PagoPendiente.objects.get(
        id_pago=id_pago
    )

    Cuota.objects.create(
        periodo=pago.mes,
        monto=pago.importe,
        fecha_pago=date.today(),
        medio_pago='Transferencia',
        estado='Pagada',
        id_tutor=pago.id_tutor,
        id_legajo_alumno=pago.legajo_alumno
    )

    pago.delete()

    return redirect('dashboard-administrativo')

def rechazar_pago(request, id_pago):

    pago = PagoPendiente.objects.get(
        id_pago=id_pago
    )

    pago.delete()

    return redirect(
        'dashboard-administrativo'
    )

@never_cache
def enviar_documentacion(request):

    if request.method != 'POST':
        return redirect('dashboard-padres')

    try:

        alumno = Alumno.objects.get(
            legajo=request.POST.get('alumno')
        )

        doc_existente = DocumentacionAlumno.objects.filter(
            legajo_alumno=alumno
        ).first()

        if doc_existente and doc_existente.estado == 'Pendiente':

            messages.error(
                request,
                'Este alumno ya tiene documentación cargada.',
                extra_tags="documentacion"
            )

            request.session["panel_activo"] = "documentacion"
            return redirect('dashboard-padres')

        if doc_existente and doc_existente.estado == 'Rechazada':
            doc_existente.delete()

        fs = FileSystemStorage(
            location='media/documentacion'
        )

        dni_frente = request.FILES.get('dni_frente')
        dni_dorso = request.FILES.get('dni_dorso')
        partida = request.FILES.get('partida')
        salud = request.FILES.get('salud')

        if not all([
            dni_frente,
            dni_dorso,
            partida,
            salud
        ]):
            raise ValueError(
                'Debe adjuntar toda la documentación requerida.'
            )

        timestamp = datetime.now().strftime(
            '%Y%m%d_%H%M%S'
        )

        ext_dni_frente = os.path.splitext(
            dni_frente.name
        )[1]

        ext_dni_dorso = os.path.splitext(
            dni_dorso.name
        )[1]

        ext_partida = os.path.splitext(
            partida.name
        )[1]

        ext_salud = os.path.splitext(
            salud.name
        )[1]

        nombre_dni_frente = (
            f'dni_frente_{alumno.legajo}_{timestamp}'
            f'{ext_dni_frente}'
        )

        nombre_dni_dorso = (
            f'dni_dorso_{alumno.legajo}_{timestamp}'
            f'{ext_dni_dorso}'
        )

        nombre_partida = (
            f'partida_{alumno.legajo}_{timestamp}'
            f'{ext_partida}'
        )

        nombre_salud = (
            f'salud_{alumno.legajo}_{timestamp}'
            f'{ext_salud}'
        )
        
        permitidos = ['.jpg', '.jpeg', '.png']
        for ext in [
            ext_dni_frente,
            ext_dni_dorso,
            ext_partida,
            ext_salud
        ]:
            if ext.lower() not in permitidos:
                raise ValueError(
                    'Todos los archivos deben ser JPG o PNG.'
                )

        ruta_dni_frente = fs.save(
            nombre_dni_frente,
            dni_frente
        )

        ruta_dni_dorso = fs.save(
            nombre_dni_dorso,
            dni_dorso
        )

        ruta_partida = fs.save(
            nombre_partida,
            partida
        )

        ruta_salud = fs.save(
            nombre_salud,
            salud
        )

        DocumentacionAlumno.objects.create(
            legajo_alumno=alumno,
            dni_frente=f'documentacion/{ruta_dni_frente}',
            dni_dorso=f'documentacion/{ruta_dni_dorso}',
            partida_nacimiento=f'documentacion/{ruta_partida}',
            certificado_salud=f'documentacion/{ruta_salud}',
            fecha_envio=timezone.now(),
            estado='Pendiente'
        )

        messages.success(
            request,
            'La documentación fue enviada correctamente.',
            extra_tags="documentacion"
        )

    except Exception as e:

        messages.error(
            request,
            f'Error al enviar la documentación: {e}',
            extra_tags="documentacion"
        )

    request.session["panel_activo"] = "documentacion"

    return redirect('dashboard-padres')

@never_cache
def aprobar_documentacion(request, id_documentacion):

    doc = get_object_or_404(
        DocumentacionAlumno,
        id_documentacion=id_documentacion
    )

    persona = obtener_persona(request)

    administrativo = PersonalAdministrativo.objects.filter(
        id_persona=persona
    ).first()

    doc.estado = "Aprobada"
    doc.fecha_revision = timezone.now()
    doc.id_administrativo = administrativo
    doc.observaciones = "Documentación aprobada."

    doc.save()

    return redirect('dashboard-administrativo')


def rechazar_documentacion(request, id_documentacion):

    doc = DocumentacionAlumno.objects.get(
        id_documentacion=id_documentacion
    )

    persona = obtener_persona(request)

    administrativo = PersonalAdministrativo.objects.filter(
        id_persona=persona
    ).first()

    doc.estado = 'Rechazada'

    doc.observaciones = request.POST.get(
        'observaciones'
    )

    doc.fecha_revision = timezone.now()

    doc.id_administrativo = administrativo

    # Eliminar archivos físicos
    archivos = [
        doc.dni_frente,
        doc.dni_dorso,
        doc.partida_nacimiento,
        doc.certificado_salud
    ]

    for archivo in archivos:

        if archivo:

            ruta = os.path.join(
                settings.MEDIA_ROOT,
                archivo
            )

            if os.path.exists(ruta):
                os.remove(ruta)

    # Vaciar rutas de archivos
    doc.dni_frente = None
    doc.dni_dorso = None
    doc.partida_nacimiento = None
    doc.certificado_salud = None

    doc.save()

    messages.success(
        request,
        'La documentación fue rechazada.'
    )

    return redirect(
        'dashboard-administrativo'
    )
    return redirect('dashboard-administrativo')

@never_cache
def list_tareas(request):
    return redirect('/docente/?panel=tareas')

@never_cache
def crear_tarea(request):
    persona = obtener_persona(request)
    if not persona:
        return redirect('login')
    
    docente = Docente.objects.filter(id_persona=persona).first()
    if not docente:
        return redirect('login')
    
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        descripcion = request.POST.get('descripcion')
        curso_id = request.POST.get('curso')
        tipo = request.POST.get('tipo', 'Tarea')
        fecha_entrega = request.POST.get('fecha')
        estado = request.POST.get('estado', 'Borrador')
        
        programar = request.POST.get('programar_publicacion') == 'on'
        fecha_pub_str = request.POST.get('fecha_publicacion')
        
        curso = Curso.objects.get(id_curso=curso_id)
        fecha_pub = None
        
        if programar and fecha_pub_str:
            from django.utils.dateparse import parse_datetime
            fecha_pub = parse_datetime(fecha_pub_str)
            estado = 'Programado'
        elif estado == 'Publicado':
            fecha_pub = timezone.now()
            
        asignacion_directa = DocenteDictaMateria.objects.filter(
            id_docente=docente,
            id_curso=curso,
        ).select_related('id_materia').first()
        if asignacion_directa:
            materia = asignacion_directa.id_materia
        else:
            materia = Materia.objects.filter(
                docentedictamateria__id_docente=docente,
                docentedictamateria__id_curso__isnull=True,
                cursocursamaterias__id_curso=curso,
            ).first()
        
        Tarea.objects.create(
            docente=docente,
            materia=materia,
            tipo=tipo,
            titulo=titulo,
            descripcion=descripcion,
            curso_destinado=curso,
            fecha=fecha_entrega if fecha_entrega else None,
            fecha_publicacion=fecha_pub,
            programa_publicacion=programar,
            estado=estado
        )
        messages.success(request, f"{tipo} creada exitosamente.")
        
    return redirect('/docente/?panel=tareas')
@never_cache
def editar_tarea(request, tarea_id):
    persona = obtener_persona(request)
    if not persona:
        return redirect('login')
    
    docente = Docente.objects.filter(id_persona=persona).first()
    if not docente:
        return redirect('login')
        
    try:
        tarea = Tarea.objects.get(id=tarea_id, docente=docente)
    except Tarea.DoesNotExist:
        messages.error(request, "La tarea no existe.")
        return redirect('/docente/?panel=tareas')
        
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        descripcion = request.POST.get('descripcion')
        curso_id = request.POST.get('curso')
        tipo = request.POST.get('tipo', 'Tarea')
        fecha_entrega = request.POST.get('fecha')
        estado = request.POST.get('estado')
        
        programar = request.POST.get('programar_publicacion') == 'on'
        fecha_pub_str = request.POST.get('fecha_publicacion')
        
        curso = Curso.objects.get(id_curso=curso_id)
        
        tarea.titulo = titulo
        tarea.descripcion = descripcion
        tarea.curso_destinado = curso
        tarea.tipo = tipo
        tarea.fecha = fecha_entrega if fecha_entrega else None
        tarea.programa_publicacion = programar
        
        if programar and fecha_pub_str:
            from django.utils.dateparse import parse_datetime
            tarea.fecha_publicacion = parse_datetime(fecha_pub_str)
            tarea.estado = 'Programado'
        else:
            tarea.estado = estado
            if estado == 'Publicado':
                tarea.fecha_publicacion = timezone.now()
            else:
                tarea.fecha_publicacion = None
                
        tarea.save()
        messages.success(request, f"{tipo} modificada exitosamente.")
        
    return redirect('/docente/?panel=tareas')
@never_cache
def borrar_tarea(request, tarea_id):
    persona = obtener_persona(request)
    if not persona:
        return redirect('login')
        
    docente = Docente.objects.filter(id_persona=persona).first()
    if not docente:
        return redirect('login')
        
    try:
        tarea = Tarea.objects.get(id=tarea_id, docente=docente)
        tipo = tarea.tipo
        tarea.delete()
        messages.success(request, f"{tipo} eliminada exitosamente.")
    except Tarea.DoesNotExist:
        messages.error(request, "La tarea no existe.")
        
    return redirect('/docente/?panel=tareas')
@never_cache
def programar_publicacion(request):
    return redirect('/docente/?panel=tareas')
@never_cache
def guardar_nota(request):
    """Vista para guardar las notas cargadas por el docente vinculándolas a su materia"""

    if request.method != 'POST':
        return redirect('dashboard-docente')

    try:
        data = json.loads(request.body)
        
        # Obtener legajo y convertir a int
        legajo_alumno_raw = data.get('legajo_alumno')
        if legajo_alumno_raw is None:
            return JsonResponse({
                'success': False, 
                'error': 'Legajo inválido'
            })
        
        try:
            legajo_alumno = int(legajo_alumno_raw)
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False, 
                'error': 'Legajo inválido'
            })

        # Obtener el docente autenticado desde la sesión
        persona = obtener_persona(request)
        if not persona:
            return JsonResponse({
                'success': False, 
                'error': 'No se encontró una sesión activa para el docente'
            })
        
        docente = Docente.objects.filter(id_persona=persona).first()
        if not docente:
            return JsonResponse({
                'success': False, 
                'error': 'El usuario actual no es un docente registrado'
            })

        # Obtener notas (pueden ser None, vacías o floats)
        nota1_raw = data.get('nota1')
        nota2_raw = data.get('nota2')
        nota3_raw = data.get('nota3')

        # Obtener el alumno por legajo
        alumno = Alumno.objects.filter(legajo=legajo_alumno).first()

        if not alumno:
            return JsonResponse({
                'success': False, 
                'error': f'No se encontró un alumno con legajo {legajo_alumno}'
            })

        # Obtener el curso del alumno
        curso = alumno.id_curso

        if not curso:
            return JsonResponse({
                'success': False, 
                'error': f'El alumno con legajo {legajo_alumno} no tiene curso asignado'
            })

        # Obtener el materia_id enviado por el frontend
        materia_id = data.get('materia_id')
        if not materia_id:
            return JsonResponse({
                'success': False,
                'error': 'No se recibió el ID de materia'
            })

        # Verificar que esa materia la dicte este docente
        asignaciones_directas = DocenteDictaMateria.objects.filter(
            id_docente=docente,
            id_curso__isnull=False,
        )
        if asignaciones_directas.exists():
            materia = Materia.objects.filter(
                id_materia=materia_id,
                docentedictamateria__id_docente=docente,
                docentedictamateria__id_curso=curso,
            ).first()
        else:
            materia = Materia.objects.filter(
                id_materia=materia_id,
                docentedictamateria__id_docente=docente,
            ).first()

        if not materia:
            return JsonResponse({
                'success': False,
                'error': 'Usted no dicta esa materia o no existe'
            })

        # Verificar que esa materia pertenezca al curso del alumno
        pertenece = CursoCursaMaterias.objects.filter(
            id_curso=curso,
            id_materia=materia
        ).exists()

        if not pertenece:
            return JsonResponse({
                'success': False,
                'error': 'Esa materia no corresponde al curso del alumno'
            })

        def procesar_nota(alumno, materia, tipo_eval, nota_raw):
            if nota_raw is None or str(nota_raw).strip() == '':
                Calificacion.objects.filter(
                    legajo_alumno=alumno,
                    id_materia=materia,
                    tipo_evaluacion=tipo_eval
                ).delete()
            else:
                try:
                    nota_val = float(nota_raw)
                    if nota_val < 0 or nota_val > 10:
                        raise ValueError("La nota debe estar entre 0 y 10")
                    Calificacion.objects.update_or_create(
                        legajo_alumno=alumno,
                        id_materia=materia,
                        tipo_evaluacion=tipo_eval,
                        defaults={'nota': nota_val, 'fecha': date.today()}
                    )
                except (ValueError, TypeError):
                    raise ValueError(f"La nota del {tipo_eval} debe ser un número válido entre 0 y 10")
        procesar_nota(alumno, materia, '1° Bimestre', nota1_raw)
        procesar_nota(alumno, materia, '2° Bimestre', nota2_raw)
        procesar_nota(alumno, materia, '3° Bimestre', nota3_raw)
        return JsonResponse({
            'success': True,
            'error': '',
            'alumno': f'{alumno.id_persona.apellido}, {alumno.id_persona.nombre}'
        })

    except ValueError as ve:
        return JsonResponse({
            'success': False,
            'error': str(ve)
        })
    except Exception as e:
        import traceback
        print("ERROR en guardar_nota:", traceback.format_exc())
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@never_cache
def guardar_observacion_justificacion(request):

    if request.method == 'POST':

        id_asistencia = request.POST.get('id_asistencia')
        observacion = request.POST.get('observacion', '').strip()

        asistencia = Asistencia.objects.filter(
            id_asistencia=id_asistencia
        ).first()

        if asistencia:
            asistencia.observacion = observacion
            asistencia.save(
                update_fields=['observacion']
            )

    return redirect(reverse('dashboard-preceptor') + '?panel=justificaciones&guardado=1')

@never_cache
def lista_alumnos_admin(request):
    """Vista para mostrar el panel de alumnos dentro del dashboard administrativo."""
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona or dashboard_url != 'dashboard-administrativo':
        return redirect('login')
    
    request.session['panel_activo'] = 'alumnos'
    
    administrativo = PersonalAdministrativo.objects.filter(id_persona=persona).first()
    instalaciones = Instalacion.objects.all()
    reservas = Reserva.objects.select_related('id_instalacion', 'id_persona_solicitante').all()
    
    if os.path.exists(OPINIONES_FILE):
        with open(OPINIONES_FILE, 'r', encoding='utf-8') as f:
            opiniones = json.load(f)
    else:
        opiniones = []
    
    cuotas = Cuota.objects.select_related('id_tutor__id_persona', 'id_legajo_alumno__id_persona')
    cuotas_pendientes = PagoPendiente.objects.exclude(estado='Pagada').count()
    solicitudes = SolicitudInscripcion.objects.all().order_by('-fecha_solicitud')
    inscripciones_pendientes = SolicitudInscripcion.objects.filter(estado="Pendiente").count()
    pagos_pendientes = PagoPendiente.objects.all()
    documentacion_pendiente = DocumentacionAlumno.objects.filter(estado='Pendiente').count()
    documentaciones = DocumentacionAlumno.objects.filter(estado='Pendiente').order_by('-fecha_envio')
    
    alumnos = Alumno.objects.select_related('id_persona', 'id_curso').all().order_by('id_persona__apellido', 'id_persona__nombre')
    cursos_disponibles = Curso.objects.select_related('nivel_educativo').all().order_by(
        'nivel_educativo__nombre', 'anio', 'comision'
    )
    
    legajo_detalle = request.GET.get('legajo')
    alumno_detalle = None
    if legajo_detalle:
        alumno_detalle = get_object_or_404(Alumno.objects.select_related('id_persona', 'id_curso'), legajo=legajo_detalle)
    
    return render(request, 'core/dashboard-administrativo.html', {
        'persona': persona, 'administrativo': administrativo, 'instalaciones': instalaciones,
        'reservas': reservas, 'opiniones': opiniones, 'cuotas': cuotas,
        'cuotas_pendientes': cuotas_pendientes, 'solicitudes': solicitudes,
        'inscripciones_pendientes': inscripciones_pendientes, 'pagos_pendientes': pagos_pendientes,
        'documentaciones': documentaciones, 'documentacion_pendiente': documentacion_pendiente,
        'panel_activo': 'alumnos', 'alumnos': alumnos, 'alumno_detalle': alumno_detalle,
        'cursos_disponibles': cursos_disponibles, # 👈 NUEVO
    })

@never_cache
def alta_alumno_admin(request):
    if request.method == 'POST':
        nombre_usuario = request.POST.get('nombre_usuario')
        contrasenia = request.POST.get('contrasenia')

        dni = request.POST.get('dni')
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        fecha_nacimiento = request.POST.get('fecha_nacimiento')
        direccion = request.POST.get('direccion')
        telefono = request.POST.get('telefono')
        email = request.POST.get('email')

        legajo = request.POST.get('legajo')
        id_curso = request.POST.get('id_curso')

        errores = []

        if not nombre_usuario:
            errores.append("El nombre de usuario es obligatorio.")

        if not contrasenia:
            errores.append("La contraseña provisoria es obligatoria.")

        if nombre_usuario and Usuario.objects.filter(
            nombre_usuario=nombre_usuario
        ).exists():
            errores.append("El nombre de usuario ya existe.")

        if legajo and Alumno.objects.filter(legajo=legajo).exists():
            errores.append("El legajo ya existe.")

        if dni and Persona.objects.filter(dni=dni).exists():
            errores.append("El DNI ya está registrado.")

        fecha_nac_obj = None
        try:
            fecha_nac_obj = datetime.strptime(
                fecha_nacimiento, '%Y-%m-%d'
            ).date()
        except (ValueError, TypeError):
            errores.append("Fecha de nacimiento inválida.")

        curso = None
        if not id_curso:
            errores.append("No se seleccionó un curso.")
        else:
            try:
                curso = Curso.objects.get(id_curso=id_curso)
            except Curso.DoesNotExist:
                errores.append("El curso seleccionado no existe.")

        if fecha_nac_obj and curso:
            hoy = date.today()
            edad = hoy.year - fecha_nac_obj.year
            if (hoy.month, hoy.day) < (fecha_nac_obj.month, fecha_nac_obj.day):
                edad -= 1

            nivel = curso.nivel_educativo.nombre.lower()
            edad_min, edad_max = None, None

            if 'inicial' in nivel:
                edad_min, edad_max = 3, 5
            elif 'primaria' in nivel or 'primario' in nivel:
                edad_min, edad_max = 6, 12
            elif 'secundaria' in nivel or 'secundario' in nivel:
                edad_min, edad_max = 13, 18

            if edad_min and edad_max:
                if edad < edad_min or edad > edad_max:
                    errores.append(
                        f"La edad del alumno ({edad} años) no corresponde al nivel "
                        f"{curso.nivel_educativo.nombre} (edades esperadas: {edad_min} a {edad_max} años)."
                    )
                    
        if errores:
            for error in errores:
                messages.error(request, error)
            return redirect('lista-alumnos-admin')

        try:
            usuario = Usuario.objects.create(
                nombre_usuario=nombre_usuario,
                contrasenia=contrasenia,
                correo=email if email else None
            )

            persona = Persona.objects.create(
                id_usuario=usuario,
                dni=dni,
                nombre=nombre,
                apellido=apellido,
                fecha_nacimiento=fecha_nac_obj,
                direccion=direccion,
                telefono=telefono,
                email=email
            )

            Alumno.objects.create(
                legajo=legajo,
                id_persona=persona,
                id_curso=curso,
                fecha_ingreso=date.today()
            )

            messages.success(
                request,
                "Alumno y cuenta de usuario registrados exitosamente."
            )

        except Exception as e:
            messages.error(
                request,
                f"Error al crear el alumno: {str(e)}"
            )

        return redirect('lista-alumnos-admin')

    return redirect('lista-alumnos-admin')

@never_cache
def modificar_alumno_admin(request, legajo):
    alumno = get_object_or_404(Alumno, legajo=legajo)
    persona = alumno.id_persona

    if request.method == 'POST':
        nuevo_dni = request.POST.get('dni')
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        fecha_nacimiento = request.POST.get('fecha_nacimiento')
        direccion = request.POST.get('direccion')
        telefono = request.POST.get('telefono')
        email = request.POST.get('email')
        id_curso = request.POST.get('id_curso')
        estado = request.POST.get('estado', 'Activo')

        errores = []

        if nuevo_dni and Persona.objects.filter(dni=nuevo_dni).exclude(id=persona.id).exists():
            errores.append("El DNI ya está registrado en otra persona.")

        fecha_nac_obj = None
        try:
            fecha_nac_obj = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            errores.append("Fecha de nacimiento inválida.")

        curso = None
        if not id_curso:
            errores.append("No se seleccionó un curso.")
        else:
            try:
                curso = Curso.objects.get(id_curso=id_curso)
            except Curso.DoesNotExist:
                errores.append("El curso seleccionado no existe.")

        if fecha_nac_obj and curso:
            hoy = date.today()
            edad = hoy.year - fecha_nac_obj.year
            if (hoy.month, hoy.day) < (fecha_nac_obj.month, fecha_nac_obj.day):
                edad -= 1

            nivel = curso.nivel_educativo.nombre.lower()
            edad_min, edad_max = None, None

            if 'inicial' in nivel:
                edad_min, edad_max = 3, 5
            elif 'primaria' in nivel or 'primario' in nivel:
                edad_min, edad_max = 6, 12
            elif 'secundaria' in nivel or 'secundario' in nivel:
                edad_min, edad_max = 13, 18

            if edad_min and edad_max:
                if edad < edad_min or edad > edad_max:
                    errores.append(
                        f"La edad del alumno ({edad} años) no corresponde al nivel "
                        f"{curso.nivel_educativo.nombre} (edades esperadas: {edad_min} a {edad_max} años)."
                    )

        if errores:
            for error in errores:
                messages.error(request, error)
            return redirect('lista-alumnos-admin')

        persona.dni = nuevo_dni
        persona.nombre = nombre
        persona.apellido = apellido
        persona.fecha_nacimiento = fecha_nac_obj
        persona.direccion = direccion
        persona.telefono = telefono
        persona.email = email
        persona.save()

        alumno.id_curso_id = id_curso
        alumno.estado = estado
        alumno.save()

        messages.success(request, "Datos del alumno actualizados correctamente.")
        return redirect('lista-alumnos-admin')

    return redirect('lista-alumnos-admin')

@never_cache
def baja_alumno_admin(request, legajo):
    if request.method == 'POST':
        alumno = get_object_or_404(Alumno, legajo=legajo)

        persona = alumno.id_persona
        usuario = persona.id_usuario

        # Primero eliminamos el alumno
        alumno.delete()

        # Después eliminamos la persona
        persona.delete()

        # Finalmente eliminamos el usuario
        if usuario:
            usuario.delete()

        messages.success(
            request,
            "Alumno, persona y usuario dados de baja correctamente."
        )

    return redirect('lista-alumnos-admin')

@never_cache
def detalle_alumno_admin(request, legajo):
    """Redirige a la lista de alumnos pasando el legajo por GET para mostrar el detalle."""
    return redirect(f"{reverse('lista-alumnos-admin')}?legajo={legajo}")
