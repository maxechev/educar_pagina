from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Obtiene un item de un diccionario usando un clave como filtro"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, '–')
    return '–'
