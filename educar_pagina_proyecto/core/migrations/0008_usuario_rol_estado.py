from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_horario_normalizado'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='rol',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='estado',
            field=models.CharField(default='Activo', max_length=20),
        ),
    ]
