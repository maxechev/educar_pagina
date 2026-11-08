# API móvil de cuotas y comprobantes

Todas las rutas requieren `Authorization: Bearer <token>` obtenido en `POST /api/auth/login/`.

## `GET /api/cuotas/`

Devuelve únicamente las cuotas de alumnos asociados al tutor autenticado. Filtros opcionales:
`?periodo=Octubre%202026` y `?estado=pendiente|parcial|pagada|vencida`.

Respuesta `200`:

```json
[
  {
    "id": 12,
    "periodo": "Octubre 2026",
    "monto_total": "45000.00",
    "monto_pagado": "15000.00",
    "saldo": "30000.00",
    "fecha_vencimiento": "2026-10-10",
    "fecha_pago": null,
    "estado": "parcial",
    "conceptos_pago": [
      {
        "clave": "cuota_base",
        "tipo": "cuota_base",
        "concepto": "Cuota base (Primario)",
        "monto": "25000.00",
        "monto_pagado": "0.00",
        "monto_en_revision": "0.00",
        "saldo_disponible": "25000.00"
      }
    ],
    "comprobantes": [
      {
        "id": 4,
        "estado": "pendiente",
        "estado_pago": "en revisión",
        "fecha_envio": "2026-10-05T18:30:00-03:00",
        "importe": "15000.00",
        "motivo_rechazo": null,
        "nombre_archivo": "comprobantes/2026/10/transferencia.pdf"
      }
    ],
    "alumno": {
      "legajo": 59,
      "nombre_completo": "Juana Acosta",
      "curso": "4° Año A - Primario"
    }
  }
]
```

Los estados de cuota son `pendiente`, `parcial`, `pagada` y `vencida`. Son independientes del
estado del comprobante, que puede ser `pendiente`, `aprobado` o `rechazado`.

## GET /api/cuotas/{id}/

Devuelve el detalle de una cuota con la misma información y validación de pertenencia que el
listado. Si la cuota no existe o corresponde a un alumno no asociado al tutor, responde 404.
El campo `discriminacion` contiene los conceptos guardados al emitir la cuota. `conceptos_pago`
incluye la clave estable y el saldo disponible de cada concepto, descontando pagos aprobados y
conceptos que ya tienen un comprobante en revisión. Para cuotas históricas sin desglose se ofrece
un único concepto `__saldo_total__`, por el saldo completo, sin atribuirlo a categorías. Para registros
anteriores a la migración de conceptos se devuelve `null`; el backend no reconstruye su detalle a
partir de inscripciones actuales, porque pueden haber cambiado.

## Generación administrativa de cuotas

En el panel administrativo, **Pagos → Generar cuotas del período** permite previsualizar y
confirmar obligaciones para un mes y vencimiento elegidos. Se consideran alumnos activos con
curso, un único tutor asociado con cuenta activa y exactamente un arancel configurado para el
nivel. Los alumnos sin esas condiciones, con varios tutores o con una cuota ya existente para el
período se muestran como omitidos. La comparación reconoce `Primaria`/`Primario` y
`Secundaria`/`Secundario` como nombres equivalentes; `Inicial` necesita su propio arancel.

La confirmación crea una `Cuota` pendiente con una copia del arancel del nivel y de los servicios
activos del alumno (hasta dos deportes, transporte y comedor). El total de la cuota es la suma de
esos conceptos. No crea un `PagoCuota` ni una solicitud de pago. El tutor podrá verla en la app si
su relación con el alumno está vigente y enviar un comprobante; ese envío queda pendiente de
revisión administrativa. Los conceptos quedan guardados en la cuota para conservar el desglose
emitido aunque luego cambien los precios o las inscripciones.

## `POST /api/comprobantes/`

Usa `multipart/form-data` con estos campos:

- `cuota_id`: entero obligatorio.
- `importe`: decimal positivo. Con selección de conceptos, debe coincidir exactamente con la suma
  de sus saldos disponibles completos.
- `conceptos_seleccionados`: lista JSON de claves devueltas por `GET /api/cuotas/`, enviada como
  texto multipart. Cada concepto se paga por el saldo completo; no se permiten pagos parciales de
  un concepto. El backend rechaza conceptos inválidos, ya pagados o en revisión.
- `medio_pago`: opcional (por defecto `Transferencia`).
- `archivo`: archivo obligatorio enviado como multipart.

Respuesta `201`:

```json
{
  "id": 4,
  "cuota_id": 12,
  "pago_id": 8,
  "estado": "en revisión",
  "mensaje": "El comprobante fue enviado y queda pendiente de revisión administrativa."
}
```

El servidor valida que la cuota pertenezca a un alumno asociado al tutor autenticado. La URL
del archivo no se expone públicamente: el nombre se informa solo como referencia. Para descargarlo,
la app usa `GET /api/comprobantes/{id}/archivo/` con el mismo token; el endpoint vuelve a validar
la relación tutor-alumno.

Los clientes anteriores que omiten `conceptos_seleccionados` conservan el envío de pagos parciales
generales; esos pagos históricos se atribuyen proporcionalmente en los reportes. Los pagos nuevos
guardan en `PagoCuota.conceptos_aplicados` el importe aplicado a cada concepto.

Al aprobar por primera vez un pago desde el panel, el sistema envía una confirmación al correo del
tutor con alumno, período, importe aprobado, estado y saldo restante. Una aprobación repetida no
envía otro correo. Si el envío falla, la aprobación queda registrada y el error se registra en el
servidor.

Errores principales: `400` para datos o archivo faltantes, selección inválida o importe que no
coincide, `403` para roles no autorizados,
`404` si la cuota no pertenece al tutor y `400` si el importe supera el saldo.

## GET /api/servicios/inscripciones/

Devuelve, para cada alumno asociado al tutor, sus inscripciones activas a deportes, transporte
y comedor. Solo se incluyen inscripciones activas y servicios/grupos activos. El resultado no
incluye alumnos asociados a otros tutores.

Los aranceles mensuales definidos por la institución se almacenan en cada deporte, recorrido y servicio de comedor: $5.000 por deporte, $10.000 por transporte y $5.000 por comedor. La migración 0017 aplica esos importes a los registros existentes y los deja como valores iniciales para nuevos servicios.

