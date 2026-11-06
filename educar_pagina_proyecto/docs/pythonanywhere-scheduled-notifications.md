# Programación de notificaciones en PythonAnywhere gratuito

PythonAnywhere Scheduled Tasks no está disponible en el plan gratuito. El workflow
`.github/workflows/notifications-pythonanywhere.yml` de GitHub Actions hace una
comprobación diaria y llama a un endpoint protegido solo el día 20 y el último día
hábil de lunes a viernes (no contempla feriados nacionales).

## Configuración necesaria

1. Desplegar este cambio en PythonAnywhere y recargar la aplicación web.
2. En la pestaña **Web**, agregar la variable de entorno
   `NOTIFICATION_SCHEDULER_TOKEN` con una clave aleatoria larga. No guardar la clave
   en el repositorio ni compartirla en chats.
3. En GitHub, en **Settings → Secrets and variables → Actions → New repository secret**,
   crear:
   - `PYTHONANYWHERE_SITE_URL`: `https://educarparatransformar.pythonanywhere.com`
   - `NOTIFICATION_SCHEDULER_TOKEN`: el mismo valor configurado en PythonAnywhere.
4. En **Actions**, habilitar workflows y ejecutar manualmente el workflow para comprobar
   que puede contactar el sitio. La ejecución manual solo verifica la fecha local y no
   enviará mensajes si no corresponde el día programado.
5. Antes del primer día real de envío, confirmar el backend SMTP y probar los comandos
   con `--dry-run` desde una consola de PythonAnywhere.

El endpoint exige POST y el encabezado `X-Scheduler-Token`. No acepta parámetros de
comando del cliente. El comando de facturación conserva su protección contra cuotas ya
existentes; no usar `--force` en la automatización. GitHub Actions puede demorar o saltar
ejecuciones programadas, por lo que revisar el historial del workflow y configurar alertas
de fallos. El calendario toma fines de semana como inhábiles, pero no tiene un calendario
de feriados; si el requisito exige feriados argentinos, debe añadirse una fuente fiable
de feriados antes de considerarlo exacto.
