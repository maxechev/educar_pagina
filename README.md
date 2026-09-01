# Página Web "Educar para Transformar"

## Descripción

Aplicación web para la gestión y comunicación de la institución educativa
"Educar para Transformar". El sistema ofrece información institucional y
herramientas diferenciadas para estudiantes, familias, docentes y personal
directivo o administrativo.

## Ejecución en local

Requisitos:

- Python 3.13 o una versión compatible con las dependencias del proyecto.
- Git, si se desea clonar el repositorio.

Desde la carpeta raíz del proyecto, crear y activar un entorno virtual:

```bash
python -m venv .venv
```

En Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

En Linux o macOS:

```bash
source .venv/bin/activate
```

Instalar las dependencias y acceder a la carpeta que contiene `manage.py`:

```bash
pip install -r requirements.txt
cd educar_pagina_proyecto
```

Ejecutar las migraciones y levantar el servidor de desarrollo:

```bash
python manage.py migrate
python manage.py runserver
```

Luego, abrir [http://127.0.0.1:8000/](http://127.0.0.1:8000/) en el navegador.

## Funcionalidades principales

- Consulta de información institucional, niveles educativos y bienestar estudiantil.
- Formulario de inscripción de nuevos estudiantes.
- Formulario de contacto y recepción de opiniones.
- Publicación y consulta de noticias y comunicados.
- Inicio de sesión con acceso a dashboards según el tipo de usuario.
- Consulta de notas, asistencias, horarios y tareas.
- Inscripción a disciplinas deportivas y envío de justificaciones.
- Gestión docente de notas, tareas y evaluaciones.
- Gestión administrativa de inscripciones, pagos, documentación y reservas.
- Gestión de usuarios y contenidos institucionales.

## Integrantes

- Navarro Fabio Ignacio
- Echeverría Maximiliano Joel
