# Calidad y colaboración

## Buenas prácticas para la revisión por pares

- Mantener cada cambio acotado a un requerimiento y explicar su propósito en el Pull Request.
- Usar nombres claros, funciones con una responsabilidad concreta y validaciones explícitas.
- Revisar permisos, errores y efectos en los datos antes de integrar cambios.
- Evitar duplicación y no incluir secretos, base de datos local, archivos temporales ni dependencias del entorno virtual.
- Acompañar cambios funcionales con pasos reproducibles y pruebas relevantes.
- La revisión debe hacerla una persona distinta de quien implementó el cambio. Registrar observaciones y su resolución.

## Flujo de Pull Request

1. Crear una rama para cada requerimiento o corrección; integrar a `main` mediante Pull Request.
2. Vincular el PR con la Issue correspondiente y completar la plantilla.
3. Esperar que Ruff y las pruebas automatizadas requeridas terminen correctamente.
4. Solicitar al menos una revisión de otra persona y responder/resolver sus comentarios.
5. Integrar solamente después de la aprobación y de resolver conversaciones.

La plantilla está en `.github/PULL_REQUEST_TEMPLATE.md`. La obligatoriedad de la revisión y de los checks se activa en GitHub con una regla de protección para `main`; el archivo local no cambia por sí mismo la configuración remota. Requiere permisos de administración del repositorio.

## Preparación del entorno de desarrollo

Con el entorno virtual activado, desde la raíz del repositorio:

```powershell
pip install -r requirements-dev.txt
pre-commit install
```

Ruff está configurado en `pyproject.toml`, recomendado para VS Code en `.vscode/`, y se ejecuta localmente antes de los commits. El hook usa Ruff del entorno virtual, por lo que hay que mantener ese entorno activado al hacer commits.

Comprobaciones manuales:

```powershell
ruff check educar_pagina_proyecto
python educar_pagina_proyecto/manage.py check
```

## Pruebas Selenium

La prueba de regresión de navegador valida que el formulario de inicio de sesión rechace credenciales incorrectas. Es independiente de los datos de producción y utiliza la base temporal de pruebas de Django.

```powershell
python educar_pagina_proyecto/manage.py test core.selenium_tests
```

Se necesita Google Chrome o Chromium instalado. Selenium Manager resuelve el driver compatible; la primera ejecución puede requerir descarga y demorar más.

## Métricas de calidad y flujo

1. **Porcentaje de escenarios Selenium aprobados:** escenarios aprobados / escenarios ejecutados × 100. Registrar el total del resultado de cada workflow de Pull Request; el objetivo es 100 % antes de integrar. Un descenso indica regresiones que requieren análisis.
2. **Tiempo de feedback de CI:** minutos entre el inicio del workflow y su finalización en cada Pull Request. Registrar mediana semanal y observar qué job concentra la demora. Sirve para detectar feedback lento y reducir el tiempo que el equipo espera antes de corregir.

GitHub Actions conserva la duración e historial de cada ejecución. La tendencia debe compararse entre períodos equivalentes; no inventar valores previos a la configuración.

## SonarQube Cloud

El workflow `.github/workflows/sonarcloud.yml` queda preparado para analizar el repositorio. Para activarlo, importar el repositorio en SonarQube Cloud y crear en GitHub Actions:

- Secreto `SONAR_TOKEN` con el token creado por el equipo.
- Variable `SONAR_ORGANIZATION` con la clave de la organización.
- Variable `SONAR_PROJECT_KEY` con la clave del proyecto.

Los nombres/valores se obtienen desde la cuenta del equipo. Nunca guardar el token en el repositorio. Hasta vincular el proyecto y completar estos valores, SonarCloud no generará análisis.
