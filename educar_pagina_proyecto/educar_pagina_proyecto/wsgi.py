import os
import sys

path = "/home/educarparatransformar/educar_pagina/educar_pagina_proyecto"

if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "educar_pagina_proyecto.settings"
)

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
