from django.urls import path

from .views import (ComprobanteArchivoView, ComprobantesView, CuotaDetalleView, CuotasView, CurrentUserView, LoginView, LogoutView, ServiciosInscripcionesView)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="mobile-login"),
    path("auth/me/", CurrentUserView.as_view(), name="mobile-current-user"),
    path("auth/logout/", LogoutView.as_view(), name="mobile-logout"),
    path("cuotas/", CuotasView.as_view(), name="mobile-cuotas"),
    path("cuotas/<int:cuota_id>/", CuotaDetalleView.as_view(), name="mobile-cuota-detalle"),
    path("servicios/inscripciones/", ServiciosInscripcionesView.as_view(), name="mobile-servicios-inscripciones"),
    path("comprobantes/", ComprobantesView.as_view(), name="mobile-comprobantes"),
    path("comprobantes/<int:comprobante_id>/archivo/", ComprobanteArchivoView.as_view(), name="mobile-comprobante-archivo"),
]
