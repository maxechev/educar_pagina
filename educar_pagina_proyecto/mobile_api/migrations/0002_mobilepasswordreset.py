from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0019_pagocuota_conceptos_aplicados"),
        ("mobile_api", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MobilePasswordReset",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code_digest", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mobile_password_resets",
                        to="core.usuario",
                    ),
                ),
            ],
            options={"db_table": "mobile_api_password_reset"},
        ),
        migrations.AddIndex(
            model_name="mobilepasswordreset",
            index=models.Index(
                fields=["user", "used_at"],
                name="mapi_reset_user_used_idx",
            ),
        ),
    ]
