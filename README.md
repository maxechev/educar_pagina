# TPI_Metodologia_Sistemas_Matech
En este repositorio está el código fuente con el cual funciona la página web del establecimiento educativo "Educar para Transformar".

## Configuración local

La aplicación usa variables de entorno para su configuración sensible. Desde la carpeta `educar_pagina_proyecto`, copiá `.env.example` como `.env` y reemplazá `SECRET_KEY` por una clave propia. El archivo `.env` es local y no debe subirse al repositorio.

Instalá las dependencias de `requirements.txt` y ejecutá la aplicación desde esa carpeta con `python manage.py runserver`.

Para producción, configurá las mismas variables directamente en el servicio de alojamiento (por ejemplo, Railway); no copies ni publiques el `.env` local. Establecé `DEBUG=False`, los dominios reales en `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`, y el backend y credenciales SMTP si se enviarán correos.
