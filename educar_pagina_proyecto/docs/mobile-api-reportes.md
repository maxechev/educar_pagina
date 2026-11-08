# Reportes financieros administrativos

Todos los endpoints requieren JWT de un usuario administrativo. `mes` debe estar entre 1 y 12 y `anio` ser al menos 2000. Si se omiten, se usa el mes y año actuales. Una fecha de vencimiento o un período guardado debe coincidir con el mes y año solicitados; no se filtra por coincidencia parcial de texto.

## Desglose financiero

`GET /api/reportes/desglose-financiero/?mes=11&anio=2026`

Agrupa importes facturados y pagos aprobados usando el detalle persistido en cada cuota:

- `deportes`: disciplina.
- `niveles`: nivel del alumno al emitir la cuota; incluye cuota base y servicios con nivel registrado.
- `horarios`: día y franja horaria del grupo deportivo.
- `docentes`: profesor responsable registrado al emitir.
- `recorridos`: recorrido de transporte registrado al emitir.

Cada fila tiene `nombre`, `facturado` y `pagado`, con montos decimales serializados como texto. Los pagos parciales se distribuyen proporcionalmente entre conceptos, redondeando a centavos. La suma se mantiene igual al importe efectivamente pagado.

Ejemplo:

```json
{
  "mes": 11,
  "anio": 2026,
  "deportes": [{"nombre": "Natación", "facturado": "5000.00", "pagado": "2500.00"}],
  "niveles": [],
  "horarios": [],
  "docentes": [],
  "recorridos": [],
  "cuotas_sin_desglose": 2,
  "facturado_sin_desglose": "50000.00",
  "pagado_sin_desglose": "10000.00"
}
```

Las cuotas históricas sin conceptos guardados se devuelven en los totales `*_sin_desglose` y no se atribuyen a categorías actuales. Esta respuesta puede tener listas vacías si no hubo conceptos categorizables en el período.

## Emisión de cuotas

Al previsualizar y confirmar cuotas desde el panel, se muestra el importe por concepto y se guarda una copia inmutable de los servicios activos y precios utilizados. Cambios futuros de precio, grupo, docente, horario, nivel o recorrido no alteran los reportes de cuotas ya emitidas. Los precios de cuotas históricas no se pueden distribuir de forma fiable si no hay copia guardada.

