from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path


def health(_request):
    return HttpResponse("ok")


urlpatterns = [
    path("health", health, name="health"),
    path("health/", health),
    path("", include("dashboard.urls")),
    path("admin/", admin.site.urls),
    path("clientes/", include("clients.urls")),
    path("reservas/", include("reservations.urls")),
    path("profesionales/", include("professionals.urls")),
    path("servicios/", include("services.urls")),
    path("atenciones/", include("performed_services.urls")),
]
