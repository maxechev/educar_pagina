import hmac
import os
from datetime import date
from calendar import monthrange

from django.core.management import call_command
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt


@method_decorator(csrf_exempt, name="dispatch")
class ScheduledNotificationView(View):
    """Authenticated webhook used by an external scheduler for monthly notices."""

    http_method_names = ["post"]

    def post(self, request, task):
        expected = os.environ.get("NOTIFICATION_SCHEDULER_TOKEN", "")
        supplied = request.headers.get("X-Scheduler-Token", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            return JsonResponse({"detail": "No autorizado."}, status=403)

        if task == "health":
            return JsonResponse({"status": "ok", "authenticated": True, "commands_executed": False})
        if task == "invoice":
            hoy = timezone.localdate()
            ultimo_dia_habil = _ultimo_dia_habil(hoy.year, hoy.month)
            if hoy != ultimo_dia_habil:
                return JsonResponse({"status": "skipped", "reason": "not_last_business_day"})
            call_command("emitir_facturas_mes", mes=hoy.month, anio=hoy.year)
        elif task == "debt-reminder":
            hoy = timezone.localdate()
            if hoy.day != 20:
                return JsonResponse({"status": "skipped", "reason": "not_day_20"})
            meses = (
                "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
            )
            call_command("enviar_recordatorios_deuda", periodo=f"{meses[hoy.month - 1]} {hoy.year}")
        else:
            return JsonResponse({"detail": "Tarea desconocida."}, status=404)

        return JsonResponse({"status": "completed", "task": task})


def _ultimo_dia_habil(year, month):
    ultimo = date(year, month, monthrange(year, month)[1])
    while ultimo.weekday() >= 5:
        ultimo = date.fromordinal(ultimo.toordinal() - 1)
    return ultimo
