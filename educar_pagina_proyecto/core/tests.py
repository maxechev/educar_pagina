from django.test import SimpleTestCase

from .templatetags.custom_tags import get_item


class GetItemFilterTests(SimpleTestCase):
    """Verifica el comportamiento compartido del filtro de diccionarios."""

    def test_returns_value_for_existing_key(self):
        self.assertEqual(get_item({'alumno': 'Ana'}, 'alumno'), 'Ana')

    def test_returns_placeholder_for_missing_key(self):
        self.assertEqual(get_item({'alumno': 'Ana'}, 'curso'), '–')

    def test_returns_placeholder_for_non_dictionary_value(self):
        self.assertEqual(get_item(None, 'curso'), '–')
