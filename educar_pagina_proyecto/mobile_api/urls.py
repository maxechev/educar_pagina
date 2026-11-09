from django.urls import path

from .views import (
    AdminComprobanteAprobarView,
    AdminComprobanteRechazarView,
    AdminComprobantesPendientesView,
    ComprobanteArchivoView,
    ComprobantesView,
    CuotaDetalleView,
    CuotasView,
    CurrentUserView,
    DeudaHistorialView,
    FacturasReporteView,
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ReporteIngresosView,
    ReportePagosCompletosView,
    ReportePagosIncompletosView,
    ReporteDesgloseFinancieroView,
    ServiciosInscripcionesView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="mobile-login"),
    path("auth/me/", CurrentUserView.as_view(), name="mobile-current-user"),
    path("auth/logout/", LogoutView.as_view(), name="mobile-logout"),
    path("auth/password-change/", PasswordChangeView.as_view(), name="mobile-password-change"),
    path("auth/password-reset/request/", PasswordResetRequestView.as_view(), name="mobile-password-reset-request"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="mobile-password-reset-confirm"),
    path("cuotas/", CuotasView.as_view(), name="mobile-cuotas"),
    path("cuotas/<int:cuota_id>/", CuotaDetalleView.as_view(), name="mobile-cuota-detalle"),
    path("servicios/inscripciones/", ServiciosInscripcionesView.as_view(), name="mobile-servicios-inscripciones"),
    path("comprobantes/", ComprobantesView.as_view(), name="mobile-comprobantes"),
    path("comprobantes/<int:comprobante_id>/archivo/", ComprobanteArchivoView.as_view(), name="mobile-comprobante-archivo"),
    # Validación administrativa de comprobantes (HU_M04)
    path("admin/comprobantes/pendientes/", AdminComprobantesPendientesView.as_view(), name="mobile-admin-comprobantes-pendientes"),
    path("admin/comprobantes/<int:pago_id>/aprobar/", AdminComprobanteAprobarView.as_view(), name="mobile-admin-comprobante-aprobar"),
    path("admin/comprobantes/<int:pago_id>/rechazar/", AdminComprobanteRechazarView.as_view(), name="mobile-admin-comprobante-rechazar"),
    # Aliases directos para la app móvil
    path("comprobantes/pendientes/", AdminComprobantesPendientesView.as_view(), name="mobile-comprobantes-pendientes"),
    path("comprobantes/<int:pago_id>/aprobar/", AdminComprobanteAprobarView.as_view(), name="mobile-comprobante-aprobar"),
    path("comprobantes/<int:pago_id>/rechazar/", AdminComprobanteRechazarView.as_view(), name="mobile-comprobante-rechazar"),
    # Reportes institucionales (Admin - HU_M10)
    path("reportes/ingresos/", ReporteIngresosView.as_view(), name="mobile-reporte-ingresos"),
    path("reportes/pagos-completos/", ReportePagosCompletosView.as_view(), name="mobile-reporte-pagos-completos"),
    path("reportes/pagos-incompletos/", ReportePagosIncompletosView.as_view(), name="mobile-reporte-pagos-incompletos"),
    path("reportes/desglose-financiero/", ReporteDesgloseFinancieroView.as_view(), name="mobile-reporte-desglose-financiero"),
    # Reportes del Tutor (HU_M08 y HU_M09)
    path("facturas/", FacturasReporteView.as_view(), name="mobile-facturas"),
    path("deuda/historial/", DeudaHistorialView.as_view(), name="mobile-deuda-historial"),
]
