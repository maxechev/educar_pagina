import requests
from django.http import JsonResponse
import re
from django.core.files.storage import FileSystemStorage
from datetime import datetime, date
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
import json
from django.core.mail import EmailMessage
from django.contrib import messages
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

@never_cache
def dashboard_alumno(request):
    persona = obtener_persona(request)

    if not persona:
        return redirect('login')
    alumno = Alumno.objects.filter(
        id_persona=persona
    ).select_related(
        'id_curso',
        'id_disciplina',
        'id_disciplina__id_instalacion',
    ).first()

    if request.method == 'POST' and request.POST.get('accion') == 'inscribir_deporte':
        request.session['panel_activo'] = 'deportes'
        id_disciplina = request.POST.get('id_disciplina')

        if not id_disciplina:
            messages.error(request, 'Debes seleccionar una disciplina.')
            return redirect('dashboard-alumno')

        disciplina_elegida = DisciplinaDeportiva.objects.filter(
            id_disciplina=id_disciplina
        ).first()

        if not disciplina_elegida:
            messages.error(request, 'La disciplina seleccionada no existe.')
            return redirect('dashboard-alumno')

        if alumno.id_disciplina_id == disciplina_elegida.id_disciplina:
            messages.info(
                request,
                f'Ya estás inscripto en {disciplina_elegida.nombre}.'
            )
            return redirect('dashboard-alumno')

        alumno.id_disciplina = disciplina_elegida
        alumno.save(update_fields=['id_disciplina'])

        messages.success(
            request,
            f'Te inscribiste correctamente en {disciplina_elegida.nombre}.'
        )
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


    curso_alumno = f"{alumno.id_curso.nivel} {alumno.id_curso.anio}° {alumno.id_curso.comision}"
    
    materias = CursoCursaMaterias.objects.filter(
        id_curso=alumno.id_curso
    ).select_related('id_materia')
    
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
        if materia.horarios:
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

    disciplina = alumno.id_disciplina
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

    disciplinas_disponibles = DisciplinaDeportiva.objects.select_related(
        'id_instalacion'
    ).all()

    for dep in disciplinas_disponibles:
        if dep.horarios:
            try:
                horarios_dep = json.loads(dep.horarios)
                horario_items = []
                for dia, hora in horarios_dep.items():
                    dia_norm = _normalize_dia(dia)
                    horario_items.append(f"{dia_norm.capitalize()}: {hora}")
                dep.horario_formateado = " | ".join(horario_items)
            except Exception:
                dep.horario_formateado = str(dep.horarios)
        else:
            dep.horario_formateado = "Sin horario"
            
    
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
        'disciplina_horario_formateado': disciplina_horario_formateado,
        'disciplinas_disponibles': disciplinas_disponibles,
        'tutor_relacion': tutor_relacion,
        'horario_por_dia': horario_por_dia,
        'hay_horarios': hay_horarios,
        "panel_activo": panel_activo,
        'tareas_alumno': tareas_alumno,
    })

@never_cache
def dashboard_docente(request):
    from django.db.models import Avg

    persona = obtener_persona(request)

    if not persona:
        return redirect('login')

    docente = Docente.objects.filter(id_persona=persona).first()

    if not docente:
        return redirect('login')

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
            'curso': getattr(curso, 'comision', str(curso)),
            'nivel': getattr(curso, 'nivel', ''),
            'turno': getattr(curso, 'turno', ''),
            'alumnos': alumnos_count,
            'promedio': round(promedio, 1) if promedio else 0,
        })

    # horarios
    horarios = CursoCursaMaterias.objects.filter(
        id_materia__in=materias
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
            horario_dict[rango][dia_cap] = f"{h.id_curso.anio}° {h.id_curso.nivel} ({h.id_curso.comision}) - {h.id_curso.turno}"

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
    })


def horario_docente(request):
    persona = obtener_persona(request)

    if not persona:
        return redirect('login')

    docente = Docente.objects.filter(id_persona=persona).first()

    if not docente:
        return redirect('login')

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
    persona = obtener_persona(request)

    if not persona:
        return redirect('login')

    cantidad_alumnos = Alumno.objects.count()
    cantidad_docentes = Docente.objects.count()
    cantidad_preceptores = Preceptor.objects.count()
    cantidad_administrativos = PersonalAdministrativo.objects.count()

    promedio_institucional = (
        Calificacion.objects.aggregate(
            promedio=Avg('nota')
        )['promedio'] or 0
    )

    ultimas_noticias = Noticia.objects.order_by(
        '-fecha_publicacion'
    )[:5]
    docentes = []

    relaciones = (
        DocenteDictaMateria.objects
        .select_related(
            'id_docente__id_persona',
            'id_materia'
        )
    )

    for relacion in relaciones[:10]:
        docente = relacion.id_docente
        materia = relacion.id_materia

        curso_materia = (
            CursoCursaMaterias.objects
            .filter(id_materia=materia)
            .select_related('id_curso')
            .first()
        )

        nivel = (
            curso_materia.id_curso.nivel
            if curso_materia
            else '-'
        )
        docentes.append({
        'nombre': f'{docente.id_persona.nombre} {docente.id_persona.apellido}',
        'materia': materia.nombre,
        'nivel': nivel,
        })
    hoy = date.today()

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
    alumnos_inicial = Alumno.objects.filter(
        id_curso__nivel='Inicial'
    ).count()

    alumnos_primario = Alumno.objects.filter(
        id_curso__nivel='Primario'
    ).count()

    alumnos_secundario = Alumno.objects.filter(
        id_curso__nivel='Secundario'
    ).count()
    solicitudes_pendientes = SolicitudInscripcion.objects.filter(
        estado='Pendiente'
    ).count()
    postulaciones = PostulacionLaboral.objects.count()
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
    persona = obtener_persona(request)

    if not persona:
        return redirect('login')

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
    
    panel_activo = request.session.pop("panel_activo", "inicio")
    
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
        'panel_activo': panel_activo,
    })

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

    curso = Curso.objects.filter(
        nivel__iexact=solicitud.nivel,
        turno__iexact=solicitud.turno
    ).first()

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

    persona = obtener_persona(request)

    if not persona:
        return redirect('login')

    tutor = Tutor.objects.filter(
        id_persona=persona
    ).first()

    hijos = []

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

        for relacion in relaciones:

            alumno = relacion.id_alumno

            promedio = Calificacion.objects.filter(
                legajo_alumno=alumno
            ).aggregate(
                promedio=Avg('nota')
            )['promedio']

            promedio = float(promedio) if promedio else 0

            if promedio:
                suma_promedios += promedio
                cantidad_promedios += 1

            pres = Asistencia.objects.filter(
                legajo_alumno=alumno,
                tipo_asistencia='Presente'
            ).count()

            aus = Asistencia.objects.filter(
                legajo_alumno=alumno,
                tipo_asistencia='Ausente'
            ).count()

            tar = Asistencia.objects.filter(
                legajo_alumno=alumno,
                tipo_asistencia='Tardanza'
            ).count()

            presentes += pres
            ausencias += aus
            tardanzas += tar
            
            documentacion = DocumentacionAlumno.objects.filter(
                legajo_alumno=alumno
            ).first()

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
    promedio_general = round(
        suma_promedios / cantidad_promedios,
        2
    ) if cantidad_promedios else 0

    total_asistencias = presentes + ausencias

    porcentaje_asistencia = round(
        (presentes / total_asistencias) * 100,
        0
    ) if total_asistencias else 0

    # 📢 COMUNICADOS (JSON) SOLO DIRECTIVOS
    COMUNICADOS_FILE = os.path.join(
        settings.BASE_DIR,
        "core",
        "comunicados.json"
    )



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

            for relacion in relaciones:

                alumno = relacion.id_alumno
                curso_alumno = f"{alumno.id_curso.nivel} {alumno.id_curso.anio}° {alumno.id_curso.comision}"

                for c in comunicados:

                    clave = (
                        c.get('titulo'),
                        c.get('fecha'),
                        c.get('rol')
                    )

                    if clave in vistos:
                        continue

                    # Directivo siempre
                    if c.get('rol') == 'Directivo':
                        comunicados_filtrados.append(c)
                        vistos.add(clave)

                    # Preceptor solo si coincide curso
                    elif (
                        c.get('rol') == 'Preceptor'
                        and c.get('curso', '').strip().lower() == curso_alumno.strip().lower()
                    ):
                        comunicados_filtrados.append(c)
                        vistos.add(clave)

            # 🔥 ORDEN CORRECTO (más nuevos primero)
            comunicados_filtrados.sort(
                key=parse_fecha,
                reverse=True
            )

        except json.JSONDecodeError:
            comunicados_filtrados = []
    panel_activo = request.session.pop("panel_activo", "inicio")
    
    cuotas_pendientes = Cuota.objects.filter(
        id_tutor=tutor,
        estado='Pendiente'
    ).count()

    cuotas = Cuota.objects.filter(
        id_tutor=tutor
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

    persona = obtener_persona(request)

    curso_id = request.POST.get('curso_id') or request.GET.get('curso_id')
    
    notificaciones = []

    if not persona:
        return redirect('login')

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
            nuevo_comunicado['curso'] = f"{curso_obj.nivel} {curso_obj.anio}° {curso_obj.comision}"

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
                nivel=curso.nivel
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
            
        materia = Materia.objects.filter(
            docentedictamateria__id_docente=docente,
            cursocursamaterias__id_curso=curso
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

        # Obtener las materias que dicta este docente
        materias_docente = Materia.objects.filter(
            docentedictamateria__id_docente=docente
        )

        # Filtrar las materias del curso del alumno que son dictadas por este docente
        materias = CursoCursaMaterias.objects.filter(
            id_curso=curso,
            id_materia__in=materias_docente
        ).select_related('id_materia')

        if not materias.exists():
            return JsonResponse({
                'success': False, 
                'error': f'Usted no dicta ninguna materia en el curso del alumno {alumno.id_persona.apellido}'
            })

        def procesar_nota(alumno, materia, tipo_eval, nota_raw):
            if nota_raw is None or str(nota_raw).strip() == '':
                # Si se borra la nota, se elimina de la base de datos si existe
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
                    
                    # Actualizar o crear la calificación para esta materia específica
                    Calificacion.objects.update_or_create(
                        legajo_alumno=alumno,
                        id_materia=materia,
                        tipo_evaluacion=tipo_eval,
                        defaults={'nota': nota_val, 'fecha': date.today()}
                    )
                except (ValueError, TypeError):
                    raise ValueError(f"La nota del {tipo_eval} debe ser un número válido entre 0 y 10")

        # Cargar las notas solo para las materias del docente en ese curso
        for curso_materia in materias:
            materia = curso_materia.id_materia
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