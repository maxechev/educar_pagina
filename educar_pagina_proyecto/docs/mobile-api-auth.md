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

## Seguridad

- Cada sesión queda registrada en la tabla mobile_api_session.
- El servidor comprueba la firma, la expiración, el estado de la cuenta y el rol en cada petición.
- El cliente debe guardar el token en SecureStore y usar HTTPS fuera del entorno local.
- La API móvil limita los intentos de login anónimos a 10 por hora.

## Aplicar cambios al backend

Instalar requirements.txt y ejecutar:

    python manage.py migrate

En desarrollo se puede iniciar Django con runserver. Para usar un teléfono físico, configurar EXPO_PUBLIC_API_URL con la IP local de la computadora; para el emulador Android usar http://10.0.2.2:8000/api/.
