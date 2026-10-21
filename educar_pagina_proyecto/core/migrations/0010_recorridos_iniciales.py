from django.db import migrations


def crear_recorridos(apps, schema_editor):
    RecorridoTransporte = apps.get_model('core', 'RecorridoTransporte')
    recorridos = [
        ('Recorrido Norte', 'Barrios del norte - escuela', 'Mañana', '07:00', 20),
        ('Recorrido Sur', 'Barrios del sur - escuela', 'Mañana', '07:00', 20),
        ('Recorrido Este', 'Barrios del este - escuela', 'Tarde', '13:00', 20),
        ('Recorrido Oeste', 'Barrios del oeste - escuela', 'Tarde', '13:00', 20),
    ]
    for nombre, descripcion, turno, hora_salida, cupo in recorridos:
        RecorridoTransporte.objects.get_or_create(
            nombre=nombre,
            defaults={
                'descripcion': descripcion,
                'turno': turno,
                'hora_salida': hora_salida,
                'cupo_maximo': cupo,
                'estado': 'Activo',
            },
        )


class Migration(migrations.Migration):
    dependencies = [('core', '0009_hu12_servicios')]
    operations = [migrations.RunPython(crear_recorridos, migrations.RunPython.noop)]
