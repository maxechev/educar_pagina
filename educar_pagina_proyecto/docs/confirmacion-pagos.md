# Confirmación de pagos aprobados

Cuando Administración aprueba un pago, el sistema conserva el pago y actualiza sus estados dentro de una transacción. Después de confirmar la transacción, envía al correo del tutor un mensaje de confirmación con un PDF adjunto; no es necesario ejecutar un comando manual en PythonAnywhere.

El PDF funciona como comprobante interno de acreditación e incluye el identificador del pago, alumno, tutor, período, fecha y medio de pago, importe aprobado, conceptos seleccionados cuando están guardados y saldo pendiente de la cuota. No es una factura fiscal.

En pagos históricos sin conceptos asociados, el PDF informa el importe como pago aplicado a la cuota, sin inferir qué rubros fueron abonados. Si el correo no puede enviarse, el pago aprobado permanece registrado y el error queda en el log del servidor.

La aprobación es idempotente: una segunda solicitud no crea otro pago ni vuelve a enviar el mensaje. No requiere una migración de base de datos. Para desplegarlo, actualizar el código del backend en PythonAnywhere y recargar la aplicación web.
