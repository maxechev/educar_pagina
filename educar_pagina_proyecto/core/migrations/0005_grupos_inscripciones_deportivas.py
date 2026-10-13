from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_niveleducativo_curso_nivel'),
    ]

    operations = [
        migrations.CreateModel(
            name='GrupoDeportivo',
            fields=[
                ('id_grupo', models.AutoField(primary_key=True, serialize=False)),
                ('dia_semana', models.CharField(max_length=20)),
                ('hora_inicio', models.TimeField()),
                ('hora_fin', models.TimeField()),
                ('cupo_maximo', models.PositiveIntegerField(blank=True, null=True)),
                ('estado', models.CharField(default='Activo', max_length=20)),
                ('id_disciplina', models.ForeignKey(db_column='id_disciplina', on_delete=django.db.models.deletion.PROTECT, related_name='grupos', to='core.disciplinadeportiva')),
                ('nivel_educativo', models.ForeignKey(db_column='id_nivel', on_delete=django.db.models.deletion.PROTECT, related_name='grupos_deportivos', to='core.niveleducativo')),
                ('profesor_responsable', models.ForeignKey(db_column='legajo_profesor', on_delete=django.db.models.deletion.PROTECT, related_name='grupos_deportivos', to='core.docente')),
            ],
            options={'db_table': 'grupo_deportivo', 'managed': True},
        ),
        migrations.CreateModel(
            name='InscripcionDeportiva',
            fields=[
                ('id_inscripcion', models.AutoField(primary_key=True, serialize=False)),
                ('fecha_inscripcion', models.DateField(auto_now_add=True)),
                ('estado', models.CharField(default='Activa', max_length=20)),
                ('id_alumno', models.ForeignKey(db_column='legajo_alumno', on_delete=django.db.models.deletion.CASCADE, related_name='inscripciones_deportivas', to='core.alumno')),
                ('id_grupo', models.ForeignKey(db_column='id_grupo', on_delete=django.db.models.deletion.CASCADE, related_name='inscripciones', to='core.grupodeportivo')),
            ],
            options={'db_table': 'inscripcion_deportiva', 'managed': True},
        ),
        migrations.AddConstraint(
            model_name='grupodeportivo',
            constraint=models.UniqueConstraint(fields=('id_disciplina', 'nivel_educativo', 'dia_semana', 'hora_inicio', 'hora_fin'), name='grupo_deportivo_unico_por_horario'),
        ),
        migrations.AddConstraint(
            model_name='inscripciondeportiva',
            constraint=models.UniqueConstraint(fields=('id_alumno', 'id_grupo'), name='inscripcion_deportiva_unica'),
        ),
    ]
