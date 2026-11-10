# API móvil: autenticación

La app usa el backend Django existente. El login web mantiene su flujo de sesión independiente.

## Endpoints disponibles

### POST /api/auth/login/

JSON:

    {"identifier":"usuario-o-correo","password":"..."}

Autentica con las credenciales existentes. Solo acepta cuentas activas de padre/tutor o administrativas. Devuelve un JWT Bearer con duración de 8 horas y los datos mínimos del usuario para abrir el panel correcto:

    {"access":"...","token_type":"Bearer","expires_in":28800,"user":{"id":1,"username":"...","name":"...","email":"...","role":"padre"}}

### GET /api/auth/me/

Requiere Authorization: Bearer <token>. Devuelve el usuario asociado a la sesión para restaurarla cuando se vuelve a abrir la app.

### POST /api/auth/logout/

Requiere Authorization: Bearer <token>. Revoca la sesión en el servidor. El token deja de servir inmediatamente.

### POST /api/auth/password-change/

Requiere Authorization: Bearer <token>. JSON:

    {"current_password":"...","new_password":"..."}

Valida la contraseña actual y aplica los validadores de contraseña de Django. Cada contraseña acepta hasta 256 caracteres. Al cambiarla, se revocan las demás sesiones móviles de la cuenta; la sesión que realizó el cambio permanece activa. Devuelve 200 con un mensaje de confirmación, o 400 con los errores de validación. Está limitado a cinco solicitudes por hora.

### POST /api/auth/password-reset/request/

Endpoint público. JSON: `{"email":"persona@correo.com"}`. Siempre devuelve el mismo mensaje genérico para no revelar si el correo está asociado a una cuenta. Para una cuenta móvil activa con correo guardado, envía un código de seis dígitos al correo. El código vence en 15 minutos; un código nuevo invalida los anteriores. Está limitado a cinco solicitudes por hora.

### POST /api/auth/password-reset/confirm/

Endpoint público. JSON: `{"email":"persona@correo.com","code":"123456","new_password":"..."}`. Valida el código de un solo uso, su vencimiento y los validadores de contraseña de Django. Se permiten hasta cinco códigos incorrectos por solicitud; el endpoint tiene además un límite de diez solicitudes por hora. Al restablecer la contraseña, revoca todas las sesiones móviles para que el usuario vuelva a iniciar sesión. Devuelve 200 al completar o 400 con un mensaje genérico si el código no es válido o venció.

### POST /api/admin/notificaciones/simulacion/

Requiere sesión móvil con rol administrativo. JSON: `{"tipo":"factura","mes":11,"anio":2026,"legajo":31}` o `{"tipo":"recordatorio","mes":11,"anio":2026,"legajo":31}`. Envía una única copia a `ADMIN_NOTIFICATION_EMAIL`, nunca al tutor ni a una dirección elegida por la app. Para esta demostración, solo se habilita si está configurado exactamente como `maxecheverri9@gmail.com` (sin distinguir mayúsculas). La factura adjunta un PDF; el recordatorio resume las deudas pendientes del tutor asociado, en todos sus períodos, excluyendo los importes cubiertos por pagos aprobados o comprobantes en revisión. No crea ni cambia cuotas, pagos o comprobantes. Está limitado a diez envíos por hora.

### GET /api/cuotas/

Requiere Authorization: Bearer <token> de padre/tutor. Devuelve las cuotas registradas para ese tutor y sus alumnos asociados. Los filtros `periodo` y `estado` son opcionales; los estados admitidos son `pendiente`, `parcial`, `pagada` y `vencida`.

Cada elemento incluye `id`, `periodo`, `monto`, `monto_pagado`, `fecha_pago`, `estado` y `alumno` (`legajo`, `nombre_completo`, `curso`). Las cuotas sin alumno vinculado al tutor autenticado no se incluyen.

La base actual registra cuotas y pagos, pero no tiene entidades de factura ni fecha de vencimiento. Por eso este endpoint no devuelve `factura_id` ni `fecha_vencimiento`; las solicitudes guardadas en `PagoPendiente` tampoco se mezclan con cuotas confirmadas. El modelo tampoco guarda cuánto se abonó en un pago parcial, así que `monto_pagado` solo es exacto para estados `Pagada`.

## Seguridad

- Cada sesión queda registrada en la tabla mobile_api_session.
- El servidor comprueba la firma, la expiración, el estado de la cuenta y el rol en cada petición.
- El cliente debe guardar el token en SecureStore y usar HTTPS fuera del entorno local.
- La API móvil limita los intentos de login anónimos a 10 por hora.
- La API limita los intentos de cambio de contraseña a 5 por hora.
- La recuperación usa códigos de un solo uso almacenados como digest, con 15 minutos de vigencia y límites de intentos. La respuesta de solicitud no revela si existe la cuenta.
- La simulación de notificaciones solo envía al buzón administrativo configurado, está limitada por tasa y no persiste datos financieros.

## Aplicar cambios al backend

Instalar requirements.txt y ejecutar:

    python manage.py migrate

En desarrollo se puede iniciar Django con runserver. Para usar un teléfono físico, configurar EXPO_PUBLIC_API_URL con la IP local de la computadora; para el emulador Android usar http://10.0.2.2:8000/api/.
