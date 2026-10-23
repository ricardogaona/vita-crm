from django.urls import path

from . import views

app_name = "ui"

urlpatterns = [
    path("", views.demo, name="demo"),
    path("estado/", views.demo_status, name="status"),
]
