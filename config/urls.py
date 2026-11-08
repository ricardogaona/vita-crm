from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("dashboard.urls")),
    path("admin/", admin.site.urls),
    path("clientes/", include("clients.urls")),
    path("reservas/", include("reservations.urls")),
    path("profesionales/", include("professionals.urls")),
    path("atenciones/", include("performed_services.urls")),
]
