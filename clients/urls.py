from django.urls import path

from . import views

app_name = "clientes"

urlpatterns = [
    path("", views.client_list, name="lista"),
    path("nueva/", views.client_create, name="nueva"),
    path("<int:pk>/", views.client_detail, name="detalle"),
    path("<int:pk>/editar/", views.client_edit, name="editar"),
    path("<int:pk>/eliminar/", views.client_delete, name="eliminar"),
]
