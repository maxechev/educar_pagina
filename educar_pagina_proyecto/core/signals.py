"""Observer de cambios de dominio para invalidar reportes y paneles."""

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import (
    Calificacion,
    CursoCursaMaterias,
    DocenteDictaMateria,
    Horario,
    InscripcionDeportiva,
    SolicitudServicio,
)


def _invalidar_reportes(**kwargs):
    version = cache.get('reportes_version', 0)
    cache.set('reportes_version', version + 1, timeout=None)
    cache.set('reportes_actualizados', True, timeout=None)


@receiver([post_save, post_delete], sender=Calificacion)
@receiver([post_save, post_delete], sender=Horario)
@receiver([post_save, post_delete], sender=CursoCursaMaterias)
@receiver([post_save, post_delete], sender=DocenteDictaMateria)
@receiver([post_save, post_delete], sender=InscripcionDeportiva)
@receiver([post_save, post_delete], sender=SolicitudServicio)
def observar_cambios_academicos(sender, **kwargs):
    _invalidar_reportes(sender=sender)
