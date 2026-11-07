from django.urls import path

from . import views

app_name = "profesionales"

urlpatterns = [
    path("", views.professional_list, name="lista"),
    path("nueva/", views.professional_create, name="nueva"),
    path("<int:pk>/", views.professional_detail, name="detalle"),
    path("<int:pk>/editar/", views.professional_edit, name="editar"),
    path("<int:pk>/desactivar/", views.professional_deactivate, name="desactivar"),
    path("<int:pk>/eliminar/", views.professional_delete, name="eliminar"),
]
