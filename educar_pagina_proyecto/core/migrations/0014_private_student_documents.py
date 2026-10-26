from pathlib import Path
import shutil

from django.conf import settings
from django.db import migrations


DOCUMENT_FIELDS = (
    'dni_frente',
    'dni_dorso',
    'partida_nacimiento',
    'certificado_salud',
)


def move_documents_to_private_storage(apps, schema_editor):
    DocumentacionAlumno = apps.get_model('core', 'DocumentacionAlumno')
    public_root = Path(settings.MEDIA_ROOT).resolve()
    private_root = Path(settings.PRIVATE_DOCUMENT_ROOT).resolve()

    for documentacion in DocumentacionAlumno.objects.all().iterator():
        for field_name in DOCUMENT_FIELDS:
            stored_path = getattr(documentacion, field_name)
            if not stored_path:
                continue

            source = (public_root / stored_path).resolve()
            destination = (private_root / stored_path).resolve()
            try:
                source.relative_to(public_root)
                destination.relative_to(private_root)
            except ValueError:
                continue

            if not source.is_file():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                source.unlink()
            else:
                shutil.move(str(source), str(destination))


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0013_alter_usuario_contrasenia'),
    ]

    operations = [
        migrations.RunPython(move_documents_to_private_storage, migrations.RunPython.noop),
    ]
