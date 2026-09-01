from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """Devuelve el valor de ``key`` en un diccionario para usarlo en templates."""
    if isinstance(mapping, dict):
        return mapping.get(key, '–')
    return '–'
