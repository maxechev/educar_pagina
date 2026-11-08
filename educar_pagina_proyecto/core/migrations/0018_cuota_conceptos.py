from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0017_disciplinadeportiva_monto_mensual_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cuota",
            name="conceptos",
            field=models.JSONField(blank=True, default=list),
        ),
    ]

