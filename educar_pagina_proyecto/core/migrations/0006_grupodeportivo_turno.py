from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_grupos_inscripciones_deportivas'),
    ]

    operations = [
        migrations.AddField(
            model_name='grupodeportivo',
            name='turno',
            field=models.CharField(default='Mañana', max_length=20),
        ),
    ]
