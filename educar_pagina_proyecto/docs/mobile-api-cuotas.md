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

Los estados de cuota son `pendiente`, `parcial`, `pagada` y `vencida`. `estado` conserva el estado
del archivo (`pendiente`, `aprobado` o `rechazado`); `estado_pago` informa el estado de la solicitud
asociada (`pendiente`, `en revisión`, `pagado` o `rechazado`). Cuando se rechaza, `motivo_rechazo`
contiene la explicación del administrador. Los tres campos pueden consultarse desde la app.

## Generación administrativa de cuotas

En el panel administrativo, **Pagos → Generar cuotas del período** permite previsualizar y
confirmar obligaciones para un mes y vencimiento elegidos. Se consideran alumnos activos con
curso, un único tutor asociado con cuenta activa y exactamente un arancel configurado para el
nivel. Los alumnos sin esas condiciones, con varios tutores o con una cuota ya existente para el
período se muestran como omitidos. La comparación reconoce `Primaria`/`Primario` y
`Secundaria`/`Secundario` como nombres equivalentes; `Inicial` necesita su propio arancel.

La confirmación crea una `Cuota` pendiente con el arancel del nivel. No crea un `PagoCuota` ni una
solicitud de pago. El tutor podrá verla en la app si su relación con el alumno está vigente y
enviar un comprobante; ese envío queda en revisión administrativa. Este generador usa
el arancel base existente y no agrega importes de deportes, transporte o comedor.

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
  "estado": "en revisión",
  "mensaje": "El comprobante fue enviado y quedó en revisión administrativa."
}
```

El servidor valida que la cuota pertenezca a un alumno asociado al tutor autenticado. La URL
del archivo no se expone públicamente: el nombre se informa solo como referencia. Para descargarlo,
la app usa `GET /api/comprobantes/{id}/archivo/` con el mismo token; el endpoint vuelve a validar
la relación tutor-alumno.

Errores principales: `400` para datos o archivo faltantes, `403` para roles no autorizados,
`404` si la cuota no pertenece al tutor y `400` si el importe supera el saldo.
