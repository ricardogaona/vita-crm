from django.urls import path

from . import views

app_name = "reservas"

urlpatterns = [
    path("", views.reservation_list, name="lista"),
    path("nueva/", views.reservation_create, name="nueva"),
    path("clientas/buscar/", views.client_search, name="clientas_buscar"),
    path("clientas/nueva/", views.client_create_modal, name="clienta_nueva"),
    path("clientas/<int:pk>/seleccionar/", views.client_select, name="clienta_seleccionar"),
    path("<int:pk>/", views.reservation_detail, name="detalle"),
    path("<int:pk>/editar/", views.reservation_edit, name="editar"),
    path("<int:pk>/eliminar/", views.reservation_delete, name="eliminar"),
]
