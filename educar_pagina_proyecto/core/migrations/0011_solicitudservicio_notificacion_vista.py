from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0010_recorridos_iniciales')]
    operations = [
        migrations.AddField(
            model_name='solicitudservicio',
            name='notificacion_vista',
            field=models.BooleanField(default=False),
        ),
    ]
