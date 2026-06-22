# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Alumno(models.Model):
    legajo = models.AutoField(primary_key=True)
    id_persona = models.ForeignKey('Persona', models.DO_NOTHING, db_column='id_persona')
    fecha_ingreso = models.DateField(blank=True, null=True)
    id_disciplina = models.ForeignKey(
        'DisciplinaDeportiva',
        models.DO_NOTHING,
        db_column='id_disciplina',
        blank=True,
        null=True,
    )
    id_curso = models.ForeignKey('Curso', models.DO_NOTHING, db_column='id_curso', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'alumno'

    def __str__(self):
        return f"{self.legajo} - {self.id_persona}"

class Asistencia(models.Model):
    id_asistencia = models.AutoField(primary_key=True)

    legajo_alumno = models.ForeignKey(
        Alumno,
        models.DO_NOTHING,
        db_column='legajo_alumno'
    )

    fecha = models.DateField(
        blank=True,
        null=True
    )

    tipo_asistencia = models.CharField(
        max_length=10,
        choices=[
            ('Presente', 'Presente'),
            ('Ausente', 'Ausente'),
            ('Tardanza', 'Tardanza')
        ]
    )

    archivo_justificacion = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    observacion = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        managed = True
        db_table = 'asistencia'

    def __str__(self):
        return f"{self.legajo_alumno} - {self.fecha} - {self.tipo_asistencia}"


class Aula(models.Model):
    id_aula = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    numero = models.IntegerField(blank=True, null=True)
    piso = models.IntegerField(blank=True, null=True)
    capacidad = models.IntegerField()
    tipo = models.CharField(max_length=50, blank=True, null=True)
    estado = models.CharField(max_length=50)

    class Meta:
        managed = True
        db_table = 'aula'


class Calificacion(models.Model):
    id_calificacion = models.AutoField(primary_key=True)
    nota = models.DecimalField(max_digits=4, decimal_places=2)
    tipo_evaluacion = models.CharField(max_length=50, blank=True, null=True)
    fecha = models.DateField()
    id_materia = models.ForeignKey('Materia', models.DO_NOTHING, db_column='id_materia')
    legajo_alumno = models.ForeignKey(Alumno, models.DO_NOTHING, db_column='legajo_alumno')

    class Meta:
        managed = True
        db_table = 'calificacion'


class Cuota(models.Model):
    id_cuota = models.AutoField(primary_key=True)

    periodo = models.CharField(max_length=20)

    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    fecha_pago = models.DateField()
    medio_pago = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )
    estado = models.CharField(
        max_length=30,
        default='Pagada'
    )
    id_tutor = models.ForeignKey(
        'Tutor',
        models.DO_NOTHING,
        db_column='id_tutor'
    )
    id_legajo_alumno = models.ForeignKey(
        'Alumno',
        models.DO_NOTHING,
        db_column='id_legajo_alumno'
    )

    class Meta:
        managed = True
        db_table = 'cuota'

class Curso(models.Model):
    id_curso = models.AutoField(primary_key=True, db_column='id')
    comision = models.CharField(max_length=20)
    anio = models.IntegerField()  # 👈 ESTE FALTA
    turno = models.CharField(max_length=30)
    nivel = models.CharField(max_length=30)
    cupo_maximo = models.IntegerField(blank=True, null=True)
    legajo_preceptor = models.ForeignKey('Preceptor', models.DO_NOTHING, db_column='legajo_preceptor', blank=True, null=True)
    id_aula = models.ForeignKey(Aula, models.DO_NOTHING, db_column='id_aula', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'curso'


class CursoCursaMaterias(models.Model):
    id_curso = models.ForeignKey(Curso, models.DO_NOTHING, db_column='id_curso')
    id_materia = models.ForeignKey('Materia', models.DO_NOTHING, db_column='id_materia')
    horarios = models.TextField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'curso_cursa_materias'


class CursoParticipaViaje(models.Model):
    id_curso = models.ForeignKey(Curso, models.DO_NOTHING, db_column='id_curso')
    id_viaje = models.ForeignKey('Viaje', models.DO_NOTHING, db_column='id_viaje')

    class Meta:
        managed = True
        db_table = 'curso_participa_viaje'


class Directivo(models.Model):
    id = models.AutoField(primary_key=True)
    id_persona = models.ForeignKey('Persona', models.DO_NOTHING, db_column='id_persona')

    class Meta:
        managed = True
        db_table = 'directivo'


class DisciplinaDeportiva(models.Model):
    id_disciplina = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    horarios = models.TextField(blank=True, null=True)
    id_instalacion = models.ForeignKey(
        'Instalacion',
        models.DO_NOTHING,
        db_column='id_instalacion',
    )

    class Meta:
        managed = True
        db_table = 'disciplina_deportiva'

    def __str__(self):
        return self.nombre


class Docente(models.Model):
    legajo = models.AutoField(primary_key=True)
    id_persona = models.ForeignKey('Persona', models.DO_NOTHING, db_column='id_persona')
    titulo = models.CharField(max_length=100)
    especialidad = models.CharField(max_length=100, blank=True, null=True)
    fecha_ingreso = models.DateField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'docente'


class DocenteDictaMateria(models.Model):
    id_docente = models.ForeignKey(Docente, models.DO_NOTHING, db_column='id_docente')
    id_materia = models.ForeignKey('Materia', models.DO_NOTHING, db_column='id_materia')

    class Meta:
        managed = True
        db_table = 'docente_dicta_materia'


class DocenteDisciplina(models.Model):
    id = models.AutoField(primary_key=True)

    legajo_docente = models.ForeignKey(
        Docente,
        models.DO_NOTHING,
        db_column='legajo_docente',
    )

    id_disciplina = models.ForeignKey(
        DisciplinaDeportiva,
        models.DO_NOTHING,
        db_column='id_disciplina',
    )

    class Meta:
        managed = True
        db_table = 'docente_disciplina'

class Evaluacion(models.Model):
    id_evaluacion = models.AutoField(primary_key=True)

    alumno = models.ForeignKey(
        'Alumno',
        on_delete=models.CASCADE,
        db_column='legajo_alumno'
    )

    docente = models.ForeignKey(
        'Docente',
        on_delete=models.CASCADE,
        db_column='legajo_docente'
    )

    materia = models.ForeignKey(
        'Materia',
        on_delete=models.CASCADE,
        db_column='id_materia'
    )

    tipo = models.CharField(max_length=50)  # Ej: Parcial, TP, Examen

    nota = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True
    )

    fecha = models.DateField()

    observacion = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.alumno} - {self.materia} - {self.nota}"

class Tarea(models.Model):
    id = models.AutoField(primary_key=True)
    
    docente = models.ForeignKey(
        'Docente', 
        on_delete=models.CASCADE,
        db_column='legajo_docente'
    )
    
    materia = models.ForeignKey(
        'Materia',
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    
    tipo = models.CharField(
        max_length=50,
        choices=[
            ('Tarea', 'Tarea'),
            ('Evaluación', 'Evaluación')
        ]
    )
    
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    fecha = models.DateField(null=True, blank=True)
    
    curso_destinado = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='tareas_docente'
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_publicacion = models.DateTimeField(blank=True, null=True)
    programa_publicacion = models.BooleanField(default=False)
    
    estado = models.CharField(
        max_length=20,
        choices=[
            ('Borrador', 'Borrador'),
            ('Publicado', 'Publicado'),
            ('Programado', 'Programado')
        ],
        default='Borrador'
    )
    
    def __str__(self):
        return f"{self.titulo} - {self.estado}"

    class Meta:
        db_table = 'tarea'

class Inscripcion(models.Model):
    id_inscripcion = models.AutoField(primary_key=True)
    fecha_inscripcion = models.DateField()
    estado = models.CharField(max_length=30)
    id_curso = models.ForeignKey(Curso, models.DO_NOTHING, db_column='id_curso')
    legajo_alumno = models.ForeignKey(Alumno, models.DO_NOTHING, db_column='legajo_alumno')

    class Meta:
        managed = True
        db_table = 'inscripcion'


class Instalacion(models.Model):
    nombre = models.CharField(max_length=100)
    capacidad = models.IntegerField()
    estado = models.CharField(max_length=50)

    class Meta:
        managed = True
        db_table = 'instalacion'


class Materia(models.Model):
    id_materia = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    carga_horaria = models.IntegerField()
    cantidad_clases = models.IntegerField()

    class Meta:
        managed = True
        db_table = 'materia'


class Noticia(models.Model):
    id_noticia = models.AutoField(primary_key=True)
    titulo = models.CharField(max_length=200)
    contenido = models.TextField(max_length=350)
    fecha_publicacion = models.DateField()

    legajo_personal = models.ForeignKey(
        'PersonalAdministrativo',
        models.DO_NOTHING,
        db_column='legajo_personal'
    )

    imagen = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    class Meta:
        managed = True
        db_table = 'noticia'


class Persona(models.Model):
    id = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        'Usuario', 
        models.DO_NOTHING, 
        db_column='id_usuario', 
        blank=True, 
        null=True)
    dni = models.CharField(unique=True, max_length=8)
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    fecha_nacimiento = models.DateField()
    direccion = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'persona'

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

class PersonalAdministrativo(models.Model):
    legajo = models.AutoField(primary_key=True)
    id_persona = models.ForeignKey(Persona, models.DO_NOTHING, db_column='id_persona')
    sector = models.CharField(max_length=50)
    cargo = models.CharField(max_length=50)
    fecha_ingreso = models.DateField()

    class Meta:
        managed = True
        db_table = 'personal_administrativo'


class Preceptor(models.Model):
    legajo = models.AutoField(primary_key=True)
    id_persona = models.ForeignKey(Persona, models.DO_NOTHING, db_column='id_persona')
    turno = models.CharField(max_length=30, blank=True, null=True)
    fecha_ingreso = models.DateField()

    class Meta:
        managed = True
        db_table = 'preceptor'


class Reserva(models.Model):
    nombre = models.CharField(max_length=100)

    fecha = models.DateField()

    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    legajo_personal_evaluador = models.ForeignKey(
        PersonalAdministrativo,
        models.DO_NOTHING,
        db_column='legajo_personal_evaluador'
    )

    id_persona_solicitante = models.ForeignKey(
        Persona,
        models.DO_NOTHING,
        db_column='id_persona_solicitante'
    )

    id_instalacion = models.ForeignKey(
        Instalacion,
        models.DO_NOTHING,
        db_column='id_instalacion'
    )

    class Meta:
        managed = True
        db_table = 'reserva'


class SolicitudViaje(models.Model):
    id_solicitud = models.AutoField(primary_key=True)
    fecha_solicitud = models.DateField()
    estado = models.CharField(max_length=50)
    observaciones = models.TextField(blank=True, null=True)
    legajo_docente = models.ForeignKey(Docente, models.DO_NOTHING, db_column='legajo_docente')

    class Meta:
        managed = True
        db_table = 'solicitud_viaje'


class Tutor(models.Model):
    id = models.AutoField(primary_key=True)
    id_persona = models.ForeignKey(Persona, models.DO_NOTHING, db_column='id_persona')
    telefono_contacto = models.CharField(max_length=20, blank=True, null=True)
    email_contacto = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'tutor'


class TutorTutoraAlumno(models.Model):
    id = models.AutoField(primary_key=True)

    id_tutor = models.ForeignKey(
        Tutor,
        models.DO_NOTHING,
        db_column='id_tutor'
    )

    id_alumno = models.ForeignKey(
        Alumno,
        models.DO_NOTHING,
        db_column='id_alumno'
    )

    tipo_parentesco = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    class Meta:
        managed = True
        db_table = 'tutor_tutora_alumno'


class Usuario(models.Model):
    id = models.AutoField(primary_key=True)
    nombre_usuario = models.CharField(unique=True, max_length=60)
    contrasenia = models.CharField(max_length=20)
    correo = models.CharField(unique=True, max_length=100, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'usuario'
        
    def __str__(self):
        return self.nombre_usuario


class Vehiculo(models.Model):
    id_vehiculo = models.AutoField(primary_key=True)
    patente = models.CharField(max_length=20)
    modelo = models.CharField(max_length=50)
    capacidad = models.IntegerField()
    estado = models.CharField(max_length=50)

    class Meta:
        managed = True
        db_table = 'vehiculo'


class Viaje(models.Model):
    id_viaje = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=50)
    fecha_salida = models.DateField()
    fecha_regreso = models.DateField()
    motivo = models.TextField()
    id_solicitud = models.OneToOneField(SolicitudViaje, models.DO_NOTHING, db_column='id_solicitud')

    class Meta:
        managed = True
        db_table = 'viaje'


class ViajeUtilizaVehiculo(models.Model):
    id_viaje = models.ForeignKey(Viaje, models.DO_NOTHING, db_column='id_viaje')
    id_vehiculo = models.ForeignKey(Vehiculo, models.DO_NOTHING, db_column='id_vehiculo')
    fecha_uso = models.DateField()

    class Meta:
        managed = True
        db_table = 'viaje_utiliza_vehiculo'

class PostulacionLaboral(models.Model):
    id = models.AutoField(primary_key=True)

    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)

    dni = models.CharField(max_length=15)

    correo = models.CharField(max_length=100)

    telefono = models.CharField(max_length=30)

    puesto = models.CharField(max_length=50)

    mensaje = models.TextField(
        blank=True,
        null=True
    )

    cv = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    fecha_postulacion = models.DateTimeField()

    class Meta:
        managed = True
        db_table = 'postulacion_laboral'

class SolicitudInscripcion(models.Model):
    id_solicitud = models.AutoField(primary_key=True)

    nombre_alumno = models.CharField(max_length=100)
    apellido_alumno = models.CharField(max_length=100)
    dni_alumno = models.CharField(max_length=8)

    fecha_nacimiento = models.DateField()

    nivel = models.CharField(max_length=30)
    turno = models.CharField(max_length=30)

    nombre_tutor = models.CharField(max_length=100)
    apellido_tutor = models.CharField(max_length=100)
    dni_tutor = models.CharField(max_length=8)

    telefono = models.CharField(max_length=20)
    email = models.CharField(max_length=100)

    direccion = models.CharField(max_length=100,blank=True,null=True)

    telefono_alumno = models.CharField(max_length=20,blank=True,null=True)

    email_alumno = models.CharField(max_length=100,blank=True,null=True)
    
    direccion_tutor = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )


    observaciones = models.TextField(
        blank=True,
        null=True
    )

    fecha_solicitud = models.DateTimeField()

    estado = models.CharField(
        max_length=30,
        default='Pendiente'
    )

    parentesco = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    class Meta:
        managed = True
        db_table = 'solicitud_inscripcion'
        
class PagoPendiente(models.Model):
    id_pago = models.AutoField(primary_key=True)

    id_tutor = models.ForeignKey(
        Tutor,
        models.DO_NOTHING,
        db_column='id_tutor'
    )

    legajo_alumno = models.ForeignKey(
        Alumno,
        models.DO_NOTHING,
        db_column='legajo_alumno'
    )

    mes = models.CharField(max_length=20)

    importe = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    estado = models.CharField(
        max_length=20,
        default='Pendiente'
    )

    fecha_solicitud = models.DateTimeField()

    class Meta:
        managed = True
        db_table = 'pago_pendiente'
        
class Arancel(models.Model):
    id_arancel = models.AutoField(primary_key=True)
    nivel = models.CharField(max_length=30)
    monto = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = True
        db_table = 'arancel'
        
class DocumentacionAlumno(models.Model):
    id_documentacion = models.AutoField(
        primary_key=True
    )

    legajo_alumno = models.ForeignKey(
        Alumno,
        models.DO_NOTHING,
        db_column='legajo_alumno'
    )

    dni_frente = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    dni_dorso = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    partida_nacimiento = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    certificado_salud = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    fecha_envio = models.DateTimeField()

    estado = models.CharField(
        max_length=20,
        default='Pendiente'
    )

    observaciones = models.TextField(
        blank=True,
        null=True
    )
    
    fecha_revision = models.DateTimeField(
        blank=True,
        null=True
    )

    id_administrativo = models.ForeignKey(
        PersonalAdministrativo,
        models.DO_NOTHING,
        db_column='id_administrativo',
        blank=True,
        null=True
    )

    class Meta:
        managed = True
        db_table = 'documentacion_alumno'