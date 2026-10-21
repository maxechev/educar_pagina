from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0011_solicitudservicio_notificacion_vista')]
    operations = [
        migrations.AlterField(
            model_name='solicitudservicio',
            name='estado',
            field=models.CharField(
                choices=[
                    ('Pendiente', 'Pendiente'),
                    ('Aprobada', 'Aprobada'),
                    ('Rechazada', 'Rechazada'),
                    ('Cancelada', 'Cancelada'),
                ],
                default='Pendiente',
                max_length=20,
            ),
        ),
    ]
