# API móvil de cuotas y comprobantes

Todas las rutas requieren `Authorization: Bearer <token>` obtenido en `POST /api/auth/login/`.

## `GET /api/cuotas/`

Devuelve únicamente las cuotas de alumnos asociados al tutor autenticado. Filtros opcionales:
`?periodo=Octubre` y `?estado=pendiente|parcial|pagada|vencida`.

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
    "comprobantes": [
      {
        "id": 4,
        "estado": "pendiente",
        "fecha_envio": "2026-10-05T18:30:00-03:00",
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

## `POST /api/comprobantes/`

Usa `multipart/form-data` con estos campos:

- `cuota_id`: entero obligatorio.
- `importe`: decimal positivo, sin superar el saldo.
- `medio_pago`: opcional (por defecto `Transferencia`).
- `archivo`: archivo obligatorio enviado como multipart.

Respuesta `201`:

```json
{
  "id": 4,
  "cuota_id": 12,
  "pago_id": 8,
  "estado": "pendiente",
  "mensaje": "El comprobante fue enviado y queda pendiente de revisión administrativa."
}
```

El servidor valida que la cuota pertenezca a un alumno asociado al tutor autenticado. La URL
del archivo no se expone públicamente: el nombre se informa solo como referencia. Para descargarlo,
la app usa `GET /api/comprobantes/{id}/archivo/` con el mismo token; el endpoint vuelve a validar
la relación tutor-alumno.

Errores principales: `400` para datos o archivo faltantes, `403` para roles no autorizados,
`404` si la cuota no pertenece al tutor y `400` si el importe supera el saldo.
