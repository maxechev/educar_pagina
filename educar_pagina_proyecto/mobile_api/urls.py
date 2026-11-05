from django.urls import path

from .views import (
    ComprobanteArchivoView,
    ComprobantesView,
    CuotaDetalleView,
    CuotasView,
    CurrentUserView,
    DeudaHistorialView,
    FacturasReporteView,
    LoginView,
    LogoutView,
    ReporteIngresosView,
    ReportePagosCompletosView,
    ReportePagosIncompletosView,
    ServiciosInscripcionesView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="mobile-login"),
    path("auth/me/", CurrentUserView.as_view(), name="mobile-current-user"),
    path("auth/logout/", LogoutView.as_view(), name="mobile-logout"),
    path("cuotas/", CuotasView.as_view(), name="mobile-cuotas"),
    path("cuotas/<int:cuota_id>/", CuotaDetalleView.as_view(), name="mobile-cuota-detalle"),
    path("servicios/inscripciones/", ServiciosInscripcionesView.as_view(), name="mobile-servicios-inscripciones"),
    path("comprobantes/", ComprobantesView.as_view(), name="mobile-comprobantes"),
    path("comprobantes/<int:comprobante_id>/archivo/", ComprobanteArchivoView.as_view(), name="mobile-comprobante-archivo"),
    # Reportes institucionales (Admin - HU_M10)
    path("reportes/ingresos/", ReporteIngresosView.as_view(), name="mobile-reporte-ingresos"),
    path("reportes/pagos-completos/", ReportePagosCompletosView.as_view(), name="mobile-reporte-pagos-completos"),
    path("reportes/pagos-incompletos/", ReportePagosIncompletosView.as_view(), name="mobile-reporte-pagos-incompletos"),
    # Reportes del Tutor (HU_M08 y HU_M09)
    path("facturas/", FacturasReporteView.as_view(), name="mobile-facturas"),
    path("deuda/historial/", DeudaHistorialView.as_view(), name="mobile-deuda-historial"),
]
