import json
from datetime import datetime
from django.db import migrations, models
import django.db.models.deletion


def convertir_horarios(apps, schema_editor):
    CursoCursaMaterias = apps.get_model('core', 'CursoCursaMaterias')
    GrupoDeportivo = apps.get_model('core', 'GrupoDeportivo')
    Horario = apps.get_model('core', 'Horario')

    def guardar(owner_field, owner, dia, rango):
        if not isinstance(rango, str) or '-' not in rango:
            return
        inicio_raw, fin_raw = rango.split('-', 1)
        try:
            inicio = datetime.strptime(inicio_raw.strip(), '%H:%M').time()
            fin = datetime.strptime(fin_raw.strip(), '%H:%M').time()
        except ValueError:
            return
        if inicio >= fin:
            return
        filtros = {owner_field: owner, 'dia_semana': dia.strip().lower(), 'hora_inicio': inicio, 'hora_fin': fin}
        Horario.objects.get_or_create(**filtros)

    for relacion in CursoCursaMaterias.objects.all():
        if not relacion.horarios:
            continue
        try:
            datos = json.loads(relacion.horarios)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(datos, dict):
            for dia, rango in datos.items():
                guardar('curso_materia', relacion, dia, rango)

    for grupo in GrupoDeportivo.objects.all():
        Horario.objects.get_or_create(
            grupo_deportivo=grupo,
            dia_semana=grupo.dia_semana.strip().lower(),
            hora_inicio=grupo.hora_inicio,
            hora_fin=grupo.hora_fin,
        )


class Migration(migrations.Migration):
    dependencies = [('core', '0006_grupodeportivo_turno')]

    operations = [
        migrations.CreateModel(
            name='Horario',
            fields=[
                ('id_horario', models.AutoField(primary_key=True, serialize=False)),
                ('dia_semana', models.CharField(max_length=20)),
                ('hora_inicio', models.TimeField()),
                ('hora_fin', models.TimeField()),
                ('curso_materia', models.ForeignKey(blank=True, db_column='id_curso_materia', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='horarios_normalizados', to='core.cursocursamaterias')),
                ('grupo_deportivo', models.ForeignKey(blank=True, db_column='id_grupo_deportivo', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='horarios_normalizados', to='core.grupodeportivo')),
            ],
            options={'db_table': 'horario', 'managed': True},
        ),
        migrations.AddConstraint(
            model_name='horario',
            constraint=models.CheckConstraint(condition=models.Q(('curso_materia__isnull', False), ('grupo_deportivo__isnull', True)) | models.Q(('curso_materia__isnull', True), ('grupo_deportivo__isnull', False)), name='horario_unico_tipo'),
        ),
        migrations.RunPython(convertir_horarios, migrations.RunPython.noop),
    ]
