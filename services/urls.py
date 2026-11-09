from django.urls import path

from . import views

app_name = "servicios"

urlpatterns = [
    path("", views.service_list, name="lista"),
    path("<int:pk>/", views.service_detail, name="detalle"),
]
