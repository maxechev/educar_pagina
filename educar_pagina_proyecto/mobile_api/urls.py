from django.urls import path

from .views import ComprobanteArchivoView, ComprobantesView, CuotasView, CurrentUserView, LoginView, LogoutView

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="mobile-login"),
    path("auth/me/", CurrentUserView.as_view(), name="mobile-current-user"),
    path("auth/logout/", LogoutView.as_view(), name="mobile-logout"),
    path("cuotas/", CuotasView.as_view(), name="mobile-cuotas"),
    path("comprobantes/", ComprobantesView.as_view(), name="mobile-comprobantes"),
    path("comprobantes/<int:comprobante_id>/archivo/", ComprobanteArchivoView.as_view(), name="mobile-comprobante-archivo"),
]
