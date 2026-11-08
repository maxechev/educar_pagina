from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_cuota_conceptos"),
    ]

    operations = [
        migrations.AddField(
            model_name="pagocuota",
            name="conceptos_aplicados",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
