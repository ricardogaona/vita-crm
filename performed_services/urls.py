from django.urls import path

from . import views

app_name = "atenciones"

urlpatterns = [
    path("", views.performed_service_list, name="lista"),
    path("nueva/", views.performed_service_create, name="nueva"),
    path("reservas/buscar/", views.reservation_search, name="reservas_buscar"),
    path(
        "reservas/<int:pk>/seleccionar/",
        views.reservation_select,
        name="reserva_seleccionar",
    ),
    path("items/fila/", views.item_row, name="item_fila"),
    path("items/precio/", views.item_price, name="precio_item"),
    path("<int:pk>/", views.performed_service_detail, name="detalle"),
    path("<int:pk>/editar/", views.performed_service_edit, name="editar"),
    path("<int:pk>/eliminar/", views.performed_service_delete, name="eliminar"),
]
