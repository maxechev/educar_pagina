from django.db import migrations, models
import django.db.models.deletion


def crear_comedor(apps, schema_editor):
    ServicioComedor = apps.get_model('core', 'ServicioComedor')
    ServicioComedor.objects.get_or_create(
        nombre='Comedor escolar',
        defaults={'cupo_maximo': 100, 'estado': 'Activo'},
    )


class Migration(migrations.Migration):
    dependencies = [('core', '0008_usuario_rol_estado')]

    operations = [
        migrations.CreateModel(
            name='RecorridoTransporte',
            fields=[
                ('id_recorrido', models.AutoField(primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=100, unique=True)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('turno', models.CharField(default='Mañana', max_length=20)),
                ('hora_salida', models.TimeField(blank=True, null=True)),
                ('cupo_maximo', models.PositiveIntegerField(default=20)),
                ('estado', models.CharField(default='Activo', max_length=20)),
            ],
            options={'db_table': 'recorrido_transporte', 'managed': True},
        ),
        migrations.CreateModel(
            name='ServicioComedor',
            fields=[
                ('id_servicio', models.AutoField(primary_key=True, serialize=False)),
                ('nombre', models.CharField(default='Comedor escolar', max_length=100, unique=True)),
                ('cupo_maximo', models.PositiveIntegerField(default=100)),
                ('estado', models.CharField(default='Activo', max_length=20)),
            ],
            options={'db_table': 'servicio_comedor', 'managed': True},
        ),
        migrations.CreateModel(
            name='InscripcionTransporte',
            fields=[
                ('id_inscripcion', models.AutoField(primary_key=True, serialize=False)),
                ('fecha_inscripcion', models.DateField(auto_now_add=True)),
                ('estado', models.CharField(default='Activa', max_length=20)),
                ('id_alumno', models.ForeignKey(db_column='legajo_alumno', on_delete=django.db.models.deletion.CASCADE, related_name='inscripciones_transporte', to='core.alumno')),
                ('id_recorrido', models.ForeignKey(db_column='id_recorrido', on_delete=django.db.models.deletion.PROTECT, related_name='inscripciones', to='core.recorridotransporte')),
            ],
            options={'db_table': 'inscripcion_transporte', 'managed': True},
        ),
        migrations.CreateModel(
            name='InscripcionComedor',
            fields=[
                ('id_inscripcion', models.AutoField(primary_key=True, serialize=False)),
                ('fecha_inscripcion', models.DateField(auto_now_add=True)),
                ('estado', models.CharField(default='Activa', max_length=20)),
                ('id_alumno', models.ForeignKey(db_column='legajo_alumno', on_delete=django.db.models.deletion.CASCADE, related_name='inscripciones_comedor', to='core.alumno')),
                ('id_servicio', models.ForeignKey(db_column='id_servicio', on_delete=django.db.models.deletion.PROTECT, related_name='inscripciones', to='core.serviciocomedor')),
            ],
            options={'db_table': 'inscripcion_comedor', 'managed': True},
        ),
        migrations.CreateModel(
            name='SolicitudServicio',
            fields=[
                ('id_solicitud', models.AutoField(primary_key=True, serialize=False)),
                ('tipo', models.CharField(choices=[('transporte', 'Transporte'), ('comedor', 'Comedor')], max_length=20)),
                ('estado', models.CharField(choices=[('Pendiente', 'Pendiente'), ('Aprobada', 'Aprobada'), ('Rechazada', 'Rechazada')], default='Pendiente', max_length=20)),
                ('fecha_solicitud', models.DateTimeField(auto_now_add=True)),
                ('observaciones', models.TextField(blank=True, null=True)),
                ('id_alumno', models.ForeignKey(db_column='legajo_alumno', on_delete=django.db.models.deletion.CASCADE, related_name='solicitudes_servicio', to='core.alumno')),
                ('id_recorrido', models.ForeignKey(blank=True, db_column='id_recorrido', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='solicitudes', to='core.recorridotransporte')),
                ('id_servicio', models.ForeignKey(blank=True, db_column='id_servicio', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='solicitudes', to='core.serviciocomedor')),
            ],
            options={'db_table': 'solicitud_servicio', 'managed': True},
        ),
        migrations.RunPython(crear_comedor, migrations.RunPython.noop),
    ]
