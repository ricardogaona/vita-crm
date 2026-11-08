from django.urls import path

from . import views

app_name = "profesionales"

urlpatterns = [
    path("", views.professional_list, name="lista"),
    path("<int:pk>/", views.professional_detail, name="detalle"),
]
