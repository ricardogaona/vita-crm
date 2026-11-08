from django.apps import AppConfig


class PerformedServicesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "performed_services"
    verbose_name = "Atenciones"

    def ready(self):
        from . import signals  # noqa: F401
