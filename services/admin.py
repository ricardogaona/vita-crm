from django.contrib import admin, messages
from django.db.models.deletion import ProtectedError

from .models import Service

DEACTIVATE_INSTEAD = (
    "Este servicio tiene atenciones registradas. Desactivalo en lugar de eliminarlo."
)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "price_gs",
        "duration_minutes",
        "is_active",
    )
    search_fields = ("code", "name")
    list_filter = ("category", "is_active")
    readonly_fields = ("created_at", "updated_at")

    def delete_view(self, request, object_id, extra_context=None):
        extra_context = {
            **(extra_context or {}),
            "deactivate_instead": DEACTIVATE_INSTEAD,
        }
        return super().delete_view(request, object_id, extra_context=extra_context)

    def delete_model(self, request, obj):
        self._delete_protecting_history(request, obj.delete)

    def delete_queryset(self, request, queryset):
        self._delete_protecting_history(request, queryset.delete)

    def _delete_protecting_history(self, request, delete):
        try:
            delete()
        except ProtectedError as exc:
            self.message_user(request, DEACTIVATE_INSTEAD, messages.ERROR)
            raise ProtectedError(DEACTIVATE_INSTEAD, exc.protected_objects) from exc
