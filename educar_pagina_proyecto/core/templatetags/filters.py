from django import template

from .custom_tags import get_item

register = template.Library()

# Se registra la implementación compartida para evitar comportamientos
# diferentes según la biblioteca de tags que cargue cada template.
register.filter('get_item', get_item)
