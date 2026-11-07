from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("clientes/", include("clients.urls")),
    path("ui/", include("ui.urls")),
]
