from django.db import migrations, models
import django.db.models.deletion


def migrar_niveles_y_cursos(apps, schema_editor):
    NivelEducativo = apps.get_model('core', 'NivelEducativo')
    Curso = apps.get_model('core', 'Curso')

    equivalencias = {
        'inicial': 'Inicial',
        'primaria': 'Primario',
        'primario': 'Primario',
        'secundaria': 'Secundario',
        'secundario': 'Secundario',
    }

    niveles = {}
    for nombre in ('Inicial', 'Primario', 'Secundario'):
        nivel, _ = NivelEducativo.objects.get_or_create(
            nombre=nombre,
            defaults={'estado': 'Activo'},
        )
        niveles[nombre] = nivel

    for curso in Curso.objects.all():
        nombre = (getattr(curso, 'nivel', '') or '').strip().lower()
        nombre_normalizado = equivalencias.get(nombre, nombre.title() or 'Inicial')
        nivel = niveles.get(nombre_normalizado)
        if nivel is None:
            nivel, _ = NivelEducativo.objects.get_or_create(
                nombre=nombre_normalizado,
                defaults={'estado': 'Activo'},
            )
        curso.nivel_educativo_id = nivel.pk
        curso.save(update_fields=['nivel_educativo'])

    # El sistema anterior podía contener cursos duplicados. Conservamos el
    # primero y movemos sus referencias antes de aplicar la restricción nueva.
    Alumno = apps.get_model('core', 'Alumno')
    CursoCursaMaterias = apps.get_model('core', 'CursoCursaMaterias')
    CursoParticipaViaje = apps.get_model('core', 'CursoParticipaViaje')
    Inscripcion = apps.get_model('core', 'Inscripcion')
    Tarea = apps.get_model('core', 'Tarea')
    DocenteDictaMateria = apps.get_model('core', 'DocenteDictaMateria')

    vistos = {}
    for curso in Curso.objects.order_by('id_curso'):
        clave = (
            curso.nivel_educativo_id,
            curso.anio,
            curso.comision.strip().lower(),
            curso.turno.strip().lower(),
        )
        if clave not in vistos:
            vistos[clave] = curso.pk
            continue

        curso_principal = vistos[clave]
        Alumno.objects.filter(id_curso_id=curso.pk).update(id_curso_id=curso_principal)
        CursoCursaMaterias.objects.filter(id_curso_id=curso.pk).update(id_curso_id=curso_principal)
        CursoParticipaViaje.objects.filter(id_curso_id=curso.pk).update(id_curso_id=curso_principal)
        Inscripcion.objects.filter(id_curso_id=curso.pk).update(id_curso_id=curso_principal)
        Tarea.objects.filter(curso_destinado_id=curso.pk).update(curso_destinado_id=curso_principal)
        DocenteDictaMateria.objects.filter(id_curso_id=curso.pk).update(id_curso_id=curso_principal)
        curso.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_docentedictamateria_id_curso'),
    ]

    operations = [
        migrations.CreateModel(
            name='NivelEducativo',
            fields=[
                ('id_nivel', models.AutoField(primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=50, unique=True)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('estado', models.CharField(
                    choices=[('Activo', 'Activo'), ('Inactivo', 'Inactivo')],
                    default='Activo',
                    max_length=20,
                )),
            ],
            options={
                'db_table': 'nivel_educativo',
                'managed': True,
                'ordering': ['nombre'],
            },
        ),
        migrations.AddField(
            model_name='curso',
            name='nivel_educativo',
            field=models.ForeignKey(
                blank=True,
                db_column='id_nivel',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cursos',
                to='core.niveleducativo',
            ),
        ),
        migrations.RunPython(migrar_niveles_y_cursos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='curso',
            name='nivel_educativo',
            field=models.ForeignKey(
                db_column='id_nivel',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cursos',
                to='core.niveleducativo',
            ),
        ),
        migrations.RemoveField(
            model_name='curso',
            name='nivel',
        ),
        migrations.AddConstraint(
            model_name='curso',
            constraint=models.UniqueConstraint(
                fields=('nivel_educativo', 'anio', 'comision', 'turno'),
                name='curso_unico_por_nivel_anio_comision_turno',
            ),
        ),
    ]
