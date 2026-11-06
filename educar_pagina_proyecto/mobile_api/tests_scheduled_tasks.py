from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase

from mobile_api.scheduled_tasks import _ultimo_dia_habil


class ScheduledNotificationTests(SimpleTestCase):
    @patch.dict("os.environ", {"NOTIFICATION_SCHEDULER_TOKEN": "test-secret"})
    def test_rejects_missing_or_invalid_token(self):
        response = self.client.post("/internal/scheduled-notifications/invoice/")
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            "/internal/scheduled-notifications/invoice/",
            HTTP_X_SCHEDULER_TOKEN="wrong",
        )
        self.assertEqual(response.status_code, 403)

    @patch.dict("os.environ", {"NOTIFICATION_SCHEDULER_TOKEN": "test-secret"})
    @patch("mobile_api.scheduled_tasks.timezone.localdate", return_value=date(2026, 11, 5))
    @patch("mobile_api.scheduled_tasks.call_command")
    def test_skips_invoice_outside_last_business_day(self, call_command, _today):
        response = self.client.post(
            "/internal/scheduled-notifications/invoice/",
            HTTP_X_SCHEDULER_TOKEN="test-secret",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "skipped")
        call_command.assert_not_called()

    def test_last_weekend_month_day_uses_friday(self):
        self.assertEqual(_ultimo_dia_habil(2026, 10), date(2026, 10, 30))
        self.assertEqual(_ultimo_dia_habil(2026, 11), date(2026, 11, 30))

    @patch.dict("os.environ", {"NOTIFICATION_SCHEDULER_TOKEN": "test-secret"})
    @patch("mobile_api.scheduled_tasks.timezone.localdate", return_value=date(2026, 11, 30))
    @patch("mobile_api.scheduled_tasks.call_command")
    def test_runs_invoice_command_on_last_business_day(self, call_command, _today):
        response = self.client.post(
            "/internal/scheduled-notifications/invoice/",
            HTTP_X_SCHEDULER_TOKEN="test-secret",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        call_command.assert_called_once_with("emitir_facturas_mes", mes=11, anio=2026)
