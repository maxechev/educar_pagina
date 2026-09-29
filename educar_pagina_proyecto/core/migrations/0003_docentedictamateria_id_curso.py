from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alumno_estado'),
    ]

    operations = [
        migrations.AddField(
            model_name='docentedictamateria',
            name='id_curso',
            field=models.ForeignKey(
                blank=True,
                db_column='id_curso',
                null=True,
                on_delete=models.DO_NOTHING,
                to='core.curso',
            ),
        ),
    ]
